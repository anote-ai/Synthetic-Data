"""
Audio synthetic data generator.
Pipeline: LLM generates script → OpenAI TTS synthesizes audio → Whisper transcribes for annotation.
"""
import os
import json
import base64
import asyncio
from pathlib import Path
from typing import List, Optional

from openai import AsyncOpenAI, OpenAI
from tqdm.auto import tqdm
import nest_asyncio

nest_asyncio.apply()

MODEL_LLM = "gpt-4o-mini"
MODEL_TTS = "tts-1"
MODEL_WHISPER = "whisper-1"
CONCURRENCY = 3
VALID_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
VALID_TTS_MODELS = {"tts-1", "tts-1-hd"}
OUTPUT_DIR = Path(os.getenv("SYNTHETIC_OUTPUT_DIR", "./outputs")) / "audio"


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)


def _get_async_client() -> AsyncOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set")
    return AsyncOpenAI(api_key=api_key)


def _build_script_prompt(prompt: str, columns: List[str], examples: List[dict], index: int) -> str:
    """Build a prompt to generate a spoken-word script."""
    columns_str = ", ".join(columns)
    base = (
        f"Generate a realistic spoken audio script (dialogue or monologue) for the following scenario:\n"
        f"Scenario: {prompt}\n"
        f"This will be row {index + 1} of a synthetic audio dataset.\n"
        f"The dataset has these columns: {columns_str}\n"
        f"Generate natural spoken language (150-300 words). Make it diverse and realistic.\n"
        f"Return ONLY the spoken text with no labels, headings, or JSON — just the words to be spoken aloud."
    )
    if examples:
        example = examples[index % len(examples)]
        if "transcript" in example:
            base += f"\n\nExample transcript for reference:\n{example['transcript']}"
    return base


async def _generate_single_audio(
    async_client: AsyncOpenAI,
    sync_client: OpenAI,
    prompt: str,
    columns: List[str],
    examples: List[dict],
    index: int,
    voice: str,
    tts_model: str,
    speed: float,
    language: Optional[str],
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audio_path = OUTPUT_DIR / f"audio_{index}.mp3"

        try:
            # Step 1: Generate script via LLM
            script_response = await async_client.chat.completions.create(
                model=MODEL_LLM,
                messages=[
                    {"role": "system", "content": "You are a scriptwriter for synthetic audio datasets. Generate natural, realistic spoken content."},
                    {"role": "user", "content": _build_script_prompt(prompt, columns, examples, index)},
                ],
                temperature=0.9,
            )
            script = script_response.choices[0].message.content.strip()

            # Step 2: TTS synthesis
            tts_response = await async_client.audio.speech.create(
                model=tts_model,
                voice=voice,
                input=script,
                speed=speed,
                response_format="mp3",
            )
            audio_bytes = tts_response.read()
            audio_path.write_bytes(audio_bytes)
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            # Step 3: Whisper transcription for ground-truth annotation
            # Use synchronous client for file upload (easier with bytes)
            transcription = sync_client.audio.transcriptions.create(
                model=MODEL_WHISPER,
                file=("audio.mp3", audio_bytes, "audio/mp3"),
                response_format="verbose_json",
                language=language,
            )

            segments = []
            if hasattr(transcription, "segments") and transcription.segments:
                for seg in transcription.segments:
                    segments.append({
                        "start": round(seg.get("start", 0), 3) if isinstance(seg, dict) else round(getattr(seg, "start", 0), 3),
                        "end": round(seg.get("end", 0), 3) if isinstance(seg, dict) else round(getattr(seg, "end", 0), 3),
                        "text": seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip(),
                    })

            row = {
                "audio_path": str(audio_path),
                "audio_base64": audio_base64,
                "script": script,
                "transcript": transcription.text if hasattr(transcription, "text") else script,
                "segments": segments,
                "language": getattr(transcription, "language", language or "en"),
                "voice": voice,
                "tts_model": tts_model,
                "status": "succeeded",
            }

            # Add any extra columns the user requested that have LLM-generated values
            extra_cols = [c for c in columns if c not in row]
            if extra_cols:
                annotation_response = await async_client.chat.completions.create(
                    model=MODEL_LLM,
                    messages=[
                        {"role": "system", "content": "Extract structured metadata from the following transcript."},
                        {"role": "user", "content": f"Transcript:\n{script}\n\nReturn a JSON object with these fields: {extra_cols}"},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                )
                import re, json as _json
                raw = annotation_response.choices[0].message.content
                try:
                    extra_data = _json.loads(raw)
                    for col in extra_cols:
                        row[col] = extra_data.get(col, "")
                except Exception:
                    for col in extra_cols:
                        row[col] = ""

            return row

        except Exception as e:
            return {"status": "failed", "error": str(e), "index": index}


async def _generate_all_audio(
    prompt: str,
    columns: List[str],
    num_rows: int,
    examples: List[dict],
    params: dict,
) -> List[dict]:
    voice = params.get("voice", "nova")
    tts_model = params.get("tts_model", MODEL_TTS)
    speed = float(params.get("speed", 1.0))
    language = params.get("language", None)
    concurrency = min(int(params.get("concurrency", CONCURRENCY)), 5)

    if voice not in VALID_VOICES:
        return [{"status": "failed", "error": f"Invalid voice '{voice}'. Must be one of: {VALID_VOICES}"}] * num_rows
    if tts_model not in VALID_TTS_MODELS:
        return [{"status": "failed", "error": f"Invalid tts_model '{tts_model}'. Must be one of: {VALID_TTS_MODELS}"}] * num_rows

    async_client = _get_async_client()
    sync_client = _get_client()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _generate_single_audio(async_client, sync_client, prompt, columns, examples, i, voice, tts_model, speed, language, semaphore)
        for i in range(num_rows)
    ]

    results = []
    with tqdm(total=num_rows, desc="Generating audio") as pbar:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            pbar.update(1)

    # Sort by index to maintain order
    results.sort(key=lambda x: x.get("index", 0) if x.get("status") == "failed" else 0)
    return results


def generate_audio_data(
    prompt: str,
    columns: List[str],
    num_rows: int = 1,
    examples: Optional[List[dict]] = None,
    params: Optional[dict] = None,
) -> List[dict]:
    """
    Generate synthetic audio data with TTS + transcription.

    Pipeline: LLM generates script → OpenAI TTS synthesizes audio → Whisper transcribes.

    Args:
        prompt: Scenario description for the audio content
        columns: Column names (transcript, language, voice, sentiment, etc.)
        num_rows: Number of audio files to generate
        examples: Optional example rows with 'transcript' key
        params: Optional dict with keys:
            - voice: alloy|echo|fable|onyx|nova|shimmer (default: nova)
            - tts_model: tts-1|tts-1-hd (default: tts-1)
            - speed: 0.25-4.0 (default: 1.0)
            - language: ISO 639-1 code (default: auto-detect)
            - concurrency: parallel requests (default: 3, max: 5)

    Returns:
        List of dicts with audio_path, audio_base64, transcript, segments, status
    """
    examples = examples or []
    params = params or {}
    return asyncio.get_event_loop().run_until_complete(
        _generate_all_audio(prompt, columns, num_rows, examples, params)
    )
