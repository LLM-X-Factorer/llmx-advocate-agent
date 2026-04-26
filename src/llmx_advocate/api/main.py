from contextlib import asynccontextmanager

from fastapi import FastAPI

from llmx_advocate import __version__
from llmx_advocate.api.routes import eval as eval_routes
from llmx_advocate.api.routes import tasks as task_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    from llmx_advocate.store.db import Base, get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title="llmx-advocate-agent",
    version=__version__,
    description="AI Engineering Advocate content production agent",
    lifespan=lifespan,
)

app.include_router(task_routes.router, prefix="/tasks", tags=["tasks"])
app.include_router(eval_routes.router, prefix="/eval", tags=["eval"])


@app.get("/")
def root() -> dict:
    return {"service": "llmx-advocate-agent", "version": __version__}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
