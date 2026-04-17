"""Tests for async video generator (issue #18)."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _import_video():
    import importlib
    import sys
    sys.modules.pop("generators.video", None)
    with patch.dict("os.environ", {"REPLICATE_API_TOKEN": "test-token"}):
        return importlib.import_module("generators.video")


class TestVideoHelpers:
    def test_parse_resolution_valid(self):
        mod = _import_video()
        assert mod._parse_resolution("576x320") == (576, 320)
        assert mod._parse_resolution("1280x720") == (1280, 720)

    def test_parse_resolution_invalid_falls_back(self):
        mod = _import_video()
        assert mod._parse_resolution("bad") == (576, 320)

    def test_output_dir_created(self, tmp_path):
        mod = _import_video()
        with patch.object(mod, "_OUTPUT_DIR", tmp_path / "video"):
            d = mod._output_dir()
            assert d.exists()


class TestVideoGenerateUnit:
    def test_no_token_returns_failed(self):
        mod = _import_video()
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(mod, "_output_dir"):
                results = mod.generate_video_data("test prompt", ["video_path"], num_rows=2)
        assert all(r["status"] == "failed" for r in results)
        assert all("REPLICATE_API_TOKEN" in r["error"] for r in results)

    def test_generate_one_success(self, tmp_path):
        mod = _import_video()

        async def _run():
            mock_client = AsyncMock()
            with patch.object(mod, "_submit_prediction", new=AsyncMock(return_value="http://poll")):
                with patch.object(mod, "_poll_prediction", new=AsyncMock(return_value="http://video.mp4")):
                    # mock video download
                    mock_client.get = AsyncMock(return_value=MagicMock(content=b"fake-video"))
                    with patch.object(mod, "_output_dir", return_value=tmp_path):
                        result = await mod._generate_one(mock_client, "token", "a cat", 0, {})
            return result

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result["status"] == "succeeded"
        assert "video_path" in result
        assert result["fps"] == 6
        assert result["frame_annotations"] == []

    def test_generate_one_with_annotation(self, tmp_path):
        mod = _import_video()

        async def _run():
            mock_client = AsyncMock()
            fake_frames = ["base64data1", "base64data2"]
            mock_annotations = [{"frame_index": 0, "description": "desc"}]
            with patch.object(mod, "_submit_prediction", new=AsyncMock(return_value="http://poll")):
                with patch.object(mod, "_poll_prediction", new=AsyncMock(return_value="http://v.mp4")):
                    mock_client.get = AsyncMock(return_value=MagicMock(content=b"fake"))
                    with patch.object(mod, "_output_dir", return_value=tmp_path):
                        with patch.object(mod, "_extract_keyframes", return_value=fake_frames):
                            with patch.object(mod, "_annotate_frames", new=AsyncMock(return_value=mock_annotations)):
                                result = await mod._generate_one(
                                    mock_client, "token", "a cat", 0,
                                    {"annotate_frames": True, "num_keyframes": 2},
                                )
            return result

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result["status"] == "succeeded"
        assert result["frame_annotations"] == [{"frame_index": 0, "description": "desc"}]

    def test_generate_one_replicate_failure(self, tmp_path):
        mod = _import_video()

        async def _run():
            mock_client = AsyncMock()
            with patch.object(mod, "_submit_prediction", new=AsyncMock(side_effect=RuntimeError("503"))):
                with patch.object(mod, "_output_dir", return_value=tmp_path):
                    result = await mod._generate_one(mock_client, "token", "prompt", 0, {})
            return result

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result["status"] == "failed"
        assert "503" in result["error"]

    def test_poll_prediction_succeeded(self):
        mod = _import_video()

        async def _run():
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(
                raise_for_status=MagicMock(),
                json=MagicMock(return_value={"status": "succeeded", "output": "http://video.mp4"}),
            ))
            with patch("asyncio.sleep", new=AsyncMock()):
                return await mod._poll_prediction(mock_client, "token", "http://poll")

        url = asyncio.get_event_loop().run_until_complete(_run())
        assert url == "http://video.mp4"

    def test_poll_prediction_failed_raises(self):
        mod = _import_video()

        async def _run():
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=MagicMock(
                raise_for_status=MagicMock(),
                json=MagicMock(return_value={"status": "failed", "error": "model crash"}),
            ))
            with patch("asyncio.sleep", new=AsyncMock()):
                await mod._poll_prediction(mock_client, "token", "http://poll")

        with pytest.raises(RuntimeError, match="failed"):
            asyncio.get_event_loop().run_until_complete(_run())

    def test_extract_keyframes_no_cv2(self):
        mod = _import_video()
        import sys
        with patch.dict(sys.modules, {"cv2": None}):
            frames = mod._extract_keyframes("nonexistent.mp4", 3)
        assert frames == []

    def test_generate_video_data_returns_list(self, tmp_path):
        mod = _import_video()
        mock_results = [{"status": "succeeded", "video_path": "p.mp4", "frame_annotations": []}]
        with patch.object(mod, "_generate_all", new=AsyncMock(return_value=mock_results)):
            results = mod.generate_video_data("test", ["video_path"], num_rows=1)
        assert results == mock_results
