from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Import routers (to be created per module)
from api.routes import text, image, video, audio, agent

app = FastAPI(
    title="Synthetic Data Generator API",
    description="API for generating synthetic datasets across multiple modalities.",
    version="1.0.0"
)

# Enable CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider limiting in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers (you'll define these in `api/routes/`)
app.include_router(text.router, prefix="/text", tags=["Text"])
app.include_router(image.router, prefix="/image", tags=["Image"])
app.include_router(video.router, prefix="/video", tags=["Video"])
app.include_router(audio.router, prefix="/audio", tags=["Audio"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])

# Optional root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the Synthetic Data Generation API!"}
