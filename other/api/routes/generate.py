

from fastapi import APIRouter, HTTPException
from api.schemas.generate import GenerateRequest
from server.database.db import insert_dataset, get_all_datasets, get_dataset_path
from generators import text, image
import os
import uuid
import shutil
from fastapi.responses import FileResponse

router = APIRouter()
DATASET_DIR = "generated_datasets"
os.makedirs(DATASET_DIR, exist_ok=True)

@router.post("/generate")
def generate(request: GenerateRequest):
    if request.type not in ["text", "image"]:
        raise HTTPException(status_code=400, detail="Only text and image are currently supported.")

    dataset_id = str(uuid.uuid4())
    dataset_path = os.path.join(DATASET_DIR, dataset_id)
    os.makedirs(dataset_path, exist_ok=True)

    if request.type == "text":
        if not request.prompt:
            raise HTTPException(status_code=400, detail="Prompt is required for text generation.")
        result = text.generate_reviews(request.prompt, num_rows=request.num_rows)
        with open(os.path.join(dataset_path, "data.csv"), "w") as f:
            f.write("review\n")
            for r in result:
                f.write(f"{r}\n")

    elif request.type == "image":
        if not request.prompt:
            request.prompt = "default image"
        image.generate_images(request.prompt, count=request.num_rows, output_dir=dataset_path)

    insert_dataset(dataset_id, request.type, dataset_path)
    return {"id": dataset_id, "type": request.type, "path": dataset_path, "download_url": f"/datasets/{dataset_id}/download"}

@router.get("/datasets")
def list_datasets():
    return get_all_datasets()

@router.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: str):
    path = get_dataset_path(dataset_id)
    if not path:
        raise HTTPException(status_code=404, detail="Dataset not found")
    zip_path = f"{path}.zip"
    shutil.make_archive(path, 'zip', path)
    return FileResponse(zip_path, media_type='application/zip', filename=f"{dataset_id}.zip")



#  from fastapi import APIRouter, HTTPException
# from api.schemas.generate import GenerateRequest
# from server.database.db import insert_dataset
# from generators import text, image, audio, video  # Import your generator modules
# import os
# import uuid

# router = APIRouter()

# DATASET_DIR = "generated_datasets"

# # Ensure directory exists
# os.makedirs(DATASET_DIR, exist_ok=True)

# @router.post("/generate")
# def generate(request: GenerateRequest):
#     # 1. Validate supported type
#     if request.type not in ["text", "image", "audio", "video"]:
#         raise HTTPException(status_code=400, detail="Invalid type. Must be text, image, audio, or video.")

#     # 2. Create a unique dataset folder
#     dataset_id = str(uuid.uuid4())
#     dataset_path = os.path.join(DATASET_DIR, f"{dataset_id}")
#     os.makedirs(dataset_path, exist_ok=True)

#     # 3. Call the appropriate generator
#     if request.type == "text":
#         if not request.prompt:
#             raise HTTPException(status_code=400, detail="Prompt is required for text generation.")
#         result = text.generate_reviews(request.prompt, num_rows=request.num_rows)
#         file_path = os.path.join(dataset_path, "data.csv")
#         with open(file_path, "w") as f:
#             f.write("review\n")
#             for line in result:
#                 f.write(f"{line}\n")

#     elif request.type == "image":
#         # Example: image.generate_images(prompt, count, output_dir)
#         image.generate_images(prompt=request.prompt, count=request.num_rows, output_dir=dataset_path)

#     elif request.type == "audio":
#         audio.generate_audio(prompt=request.prompt, output_dir=dataset_path)

#     elif request.type == "video":
#         video.generate_video(prompt=request.prompt, output_dir=dataset_path)

#     # 4. Save metadata in DB
#     insert_dataset(dataset_id, request.type, dataset_path)

#     # 5. Return response
#     return {"id": dataset_id, "type": request.type, "path": dataset_path, "download_url": f"/datasets/{dataset_id}/download"}

# from fastapi.responses import FileResponse
# from server.database.db import get_all_datasets, get_dataset_path
# import shutil

# @router.get("/datasets")
# def list_datasets():
#     return get_all_datasets()

# @router.get("/datasets/{dataset_id}/download")
# def download_dataset(dataset_id: str):
#     path = get_dataset_path(dataset_id)
#     if not path:
#         raise HTTPException(status_code=404, detail="Dataset not found")

#     zip_path = f"{path}.zip"
#     shutil.make_archive(path, 'zip', path)
#     return FileResponse(zip_path, media_type='application/zip', filename=f"{dataset_id}.zip")




# from fastapi import APIRouter, HTTPException
# from api.schemas.generate import GenerateRequest
# from other.api.generators.text import text_generator
# # from api.generators import video_generation  # Uncomment when API key is available

# router = APIRouter()

# @router.post("/generate")
# def generate(request: GenerateRequest):
#     if request.type == "text":
#         if not request.prompt:
#             raise HTTPException(status_code=400, detail="Prompt is required for text generation.")
#         result = text_generator.generate_reviews(request.prompt, num_rows=request.num_rows)
#         return {"result": result}
#     # elif request.type == "video":
#     #     # Uncomment and implement when API key is available
#     #     result = video_generation.generate_video(request.prompt)
#     #     return {"result": result}
#     else:
#         raise HTTPException(status_code=400, detail="Invalid or unsupported type specified. Only 'text' is currently supported.")
    
