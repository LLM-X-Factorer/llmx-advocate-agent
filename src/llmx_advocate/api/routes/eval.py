from fastapi import APIRouter, HTTPException

from llmx_advocate.core.models import OpeningStyle

router = APIRouter()


@router.post("/fork/{task_id}")
async def fork_task(task_id: str, model: str, opening_style: OpeningStyle | None = None) -> dict:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.get("/compare")
async def compare_tasks(task_a_id: str, task_b_id: str) -> dict:
    raise HTTPException(status_code=501, detail="not implemented yet")


@router.post("/batch")
async def eval_batch(source: dict, models: list[str], opening_styles: list[OpeningStyle] | None = None) -> dict:
    raise HTTPException(status_code=501, detail="not implemented yet")
