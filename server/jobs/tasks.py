"""
RQ job tasks for async generation.
These functions are called by the RQ worker process.
"""
import sys
import os

# Ensure server/ is on the path when running as a worker
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def run_generation(task_type, prompt, columns, num_rows, examples, params, user_email):
    """
    Run a synthetic data generation job.
    Called by the RQ worker. Returns a result dict.
    """
    try:
        from api_endpoints.handler import GENERATOR_MAP
        generator_fn = GENERATOR_MAP.get(task_type)
        if not generator_fn:
            return {"status": "failed", "error": f"Unknown task_type: {task_type}"}
        data = generator_fn(
            prompt=prompt,
            columns=columns,
            num_rows=num_rows,
            examples=examples or [],
            params=params or {},
        )
        return {"status": "completed", "data": data, "row_count": len(data)}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
