from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from llmx_advocate.api.deps import db_session as db_session_dep
from llmx_advocate.api.main import app

FIXTURES = Path(__file__).parent.parent / "fixtures" / "example-pack"


@pytest.fixture
async def client(db_session) -> AsyncIterator[httpx.AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[db_session_dep] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_fork_creates_new_task_with_overrides(client):
    pack = (FIXTURES / "scout-pack-example.md").read_text(encoding="utf-8")
    create = await client.post("/tasks", json={"title": "src", "source": {"pack_content": pack}})
    src_id = create.json()["task"]["id"]

    r = await client.post(
        f"/eval/fork/{src_id}",
        json={
            "title_suffix": "ds-r1",
            "llm_model": "deepseek/deepseek-r1",
            "opening_style": "suspense_first",
            "run_immediately": True,
            "run_async": False,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    new_task = body["task"]
    assert new_task["id"] != src_id
    assert new_task["config"]["llm_model"] == "deepseek/deepseek-r1"
    assert new_task["config"]["opening_style"] == "suspense_first"


@pytest.mark.asyncio
async def test_fork_404_for_unknown_source(client):
    r = await client.post(
        "/eval/fork/01HXNOSUCH",
        json={"run_immediately": False},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_compare_two_tasks(client):
    pack = (FIXTURES / "scout-pack-example.md").read_text(encoding="utf-8")
    a = await client.post("/tasks", json={"title": "a", "source": {"pack_content": pack}})
    a_id = a.json()["task"]["id"]

    fork = await client.post(
        f"/eval/fork/{a_id}",
        json={
            "title_suffix": "b",
            "llm_model": "deepseek/deepseek-r1",
            "run_immediately": True,
            "run_async": False,
        },
    )
    b_id = fork.json()["task"]["id"]

    r = await client.get("/eval/compare", params={"a": a_id, "b": b_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["comparison"]["a_id"] == a_id
    assert body["comparison"]["b_id"] == b_id
    assert "llm_model" in body["config_diff"]
    assert body["config_diff"]["llm_model"]["b"] == "deepseek/deepseek-r1"
    assert len(body["comparison"]["phase_summary"]) >= 1


@pytest.mark.asyncio
async def test_compare_404_when_task_missing(client):
    r = await client.get("/eval/compare", params={"a": "01HXNO1", "b": "01HXNO2"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_batch_creates_multiple_tasks(client):
    pack = (FIXTURES / "scout-pack-example.md").read_text(encoding="utf-8")
    r = await client.post(
        "/eval/batch",
        json={
            "source_pack_content": pack,
            "title": "smoke",
            "models": ["deepseek/deepseek-chat", "deepseek/deepseek-r1"],
            "opening_styles": ["judgment_first", "suspense_first"],
            "run_async": False,
        },
    )
    assert r.status_code == 200, r.text
    task_ids = r.json()["task_ids"]
    # 2 models × 2 styles = 4 tasks.
    assert len(task_ids) == 4


@pytest.mark.asyncio
async def test_batch_rejects_empty_models(client):
    pack = (FIXTURES / "scout-pack-example.md").read_text(encoding="utf-8")
    r = await client.post(
        "/eval/batch",
        json={"source_pack_content": pack, "models": []},
    )
    assert r.status_code == 400
