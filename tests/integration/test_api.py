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
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_task_completes_full_pipeline(client):
    """All 9 phases implemented — task reaches COMPLETED end-to-end via API."""
    pack = (FIXTURES / "scout-pack-example.md").read_text(encoding="utf-8")
    r = await client.post(
        "/tasks",
        json={
            "title": "scout pack via api",
            "source": {"pack_content": pack},
        },
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["task"]["status"] == "completed"
    assert body["task"]["current_phase"] == "P6"
    by_phase = {r["phase_id"]: r for r in body["runs"]}
    for pid in ("P1", "P1.5", "P2", "P2.5", "P2.6", "P3", "P4", "P5", "P6"):
        assert by_phase[pid]["status"] == "passed", f"{pid} should pass"


@pytest.mark.asyncio
async def test_create_task_rejects_empty_source(client):
    r = await client.post("/tasks", json={"title": "x", "source": {}})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_task_after_create(client):
    pack = (FIXTURES / "manual-pack-example.md").read_text(encoding="utf-8")
    create = await client.post("/tasks", json={"title": "t", "source": {"pack_content": pack}})
    task_id = create.json()["task"]["id"]

    r = await client.get(f"/tasks/{task_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["task"]["id"] == task_id


@pytest.mark.asyncio
async def test_get_task_404(client):
    r = await client.get("/tasks/01HX_does_not_exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks(client):
    pack = (FIXTURES / "manual-pack-example.md").read_text(encoding="utf-8")
    await client.post("/tasks", json={"title": "a", "source": {"pack_content": pack}})
    await client.post("/tasks", json={"title": "b", "source": {"pack_content": pack}})

    r = await client.get("/tasks")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2


@pytest.mark.asyncio
async def test_run_action_is_idempotent_for_completed_task(client):
    """A completed task that's POST-actions/run again is idempotent (no extra runs)."""
    pack = (FIXTURES / "manual-pack-example.md").read_text(encoding="utf-8")
    create = await client.post("/tasks", json={"title": "t", "source": {"pack_content": pack}})
    task_id = create.json()["task"]["id"]
    assert create.json()["task"]["status"] == "completed"

    runs_before = len(create.json()["runs"])
    r = await client.post(f"/tasks/{task_id}/actions/run")
    assert r.status_code == 200
    body = r.json()
    assert body["task"]["status"] == "completed"
    assert len(body["runs"]) == runs_before  # no new runs


@pytest.mark.asyncio
async def test_pause_action(client):
    pack = (FIXTURES / "manual-pack-example.md").read_text(encoding="utf-8")
    create = await client.post("/tasks", json={"title": "t", "source": {"pack_content": pack}})
    task_id = create.json()["task"]["id"]

    r = await client.post(f"/tasks/{task_id}/actions/pause")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_phase_runs_filtered(client):
    pack = (FIXTURES / "manual-pack-example.md").read_text(encoding="utf-8")
    create = await client.post("/tasks", json={"title": "t", "source": {"pack_content": pack}})
    task_id = create.json()["task"]["id"]

    r = await client.get(f"/tasks/{task_id}/phases/P1")
    assert r.status_code == 200
    runs = r.json()
    assert len(runs) == 1
    assert runs[0]["phase_id"] == "P1"
    assert runs[0]["status"] == "passed"
