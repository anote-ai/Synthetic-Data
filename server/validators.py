from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
import os

VALID_TASK_TYPES = {"text", "image", "video", "audio", "agent", "pii", "language"}
MAX_ROWS = int(os.getenv("MAX_ROWS_PER_REQUEST", "100"))

class GenerateRequest(BaseModel):
    task_type: str = Field(..., description="Modality to generate")
    prompt: str = Field(..., min_length=1, description="Generation prompt")
    num_rows: int = Field(default=5, ge=1, le=MAX_ROWS, description="Number of rows to generate")
    columns: List[str] = Field(..., min_length=1, description="Column names for output")
    examples: Optional[List[dict]] = Field(default=[], description="Few-shot examples")
    params: Optional[dict] = Field(default={}, description="Modality-specific parameters")

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v):
        if v not in VALID_TASK_TYPES:
            raise ValueError(f"task_type must be one of: {', '.join(sorted(VALID_TASK_TYPES))}")
        return v

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v):
        if not v:
            raise ValueError("columns must be a non-empty list")
        for col in v:
            if not isinstance(col, str) or not col.strip():
                raise ValueError("Each column must be a non-empty string")
        return [c.strip() for c in v]
