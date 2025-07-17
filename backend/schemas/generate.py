from pydantic import BaseModel
from typing import Optional

class GenerateRequest(BaseModel):
    type: str  # "text", "image", "video", "audio", "agent"
    prompt: Optional[str] = None
    num_rows: Optional[int] = 10
    columns: Optional[list[str]] = None
    # Add other fields as needed for other generators