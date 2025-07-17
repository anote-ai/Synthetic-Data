from fastapi import APIRouter, HTTPException
from backend.schemas.generate import GenerateRequest
from generators import text_generator
# from api.generators import video_generation  # Uncomment when API key is available

router = APIRouter()

@router.post("/generate")
def generate(request: GenerateRequest):
    if request.type == "text":
        if not request.prompt:
            raise HTTPException(status_code=400, detail="Prompt is required for text generation.")
        result = text_generator.generate_reviews(request.prompt, num_rows=request.num_rows)
        return {"result": result}
    # elif request.type == "video":
    #     # Uncomment and implement when API key is available
    #     result = video_generation.generate_video(request.prompt)
    #     return {"result": result}
    else:
        raise HTTPException(status_code=400, detail="Invalid or unsupported type specified. Only 'text' is currently supported.")