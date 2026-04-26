import json
from importlib.resources import files
from typing import Any


def video_json_schema() -> dict[str, Any]:
    """Load the canonical Video JSON schema (draft-07) from VIDEO_JSON_REFERENCE.md."""
    path = files("llmx_advocate.core.schemas").joinpath("video_json.schema.json")
    return json.loads(path.read_text(encoding="utf-8"))
