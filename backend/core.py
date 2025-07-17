from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from backend.routes import app

# Load environment variables from .env
load_dotenv()

# Import routers (to be created per module)
from backend.routes import app

app_main = FastAPI(
    title="Synthetic Data Generator API",
    description="API for generating synthetic datasets across multiple modalities.",
    version="1.0.0"
)

# Enable CORS (adjust origins as needed)
app_main.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider limiting in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers (you'll define these in `api/routes/`)
app_main.include_router(app.router, prefix="/api", tags=["Generate"])

# Optional root endpoint
@app_main.get("/")
def read_root():
    return {"message": "Welcome to the Synthetic Data Generation API!"}



#to run the application: uvicorn backend.core:app_main --reload
