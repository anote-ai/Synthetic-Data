# DEPRECATED: This FastAPI prototype is no longer maintained.
# The canonical API is the Flask app in server/. See README.md for setup.
# Kept for historical reference only — do not use in production.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from api.routes import generate

# Load environment variables from .env
load_dotenv()

# Import routers (to be created per module)
from api.routes import generate

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
app.include_router(generate.router, prefix="/api", tags=["Generate"])

# Optional root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the Synthetic Data Generation API!"}
