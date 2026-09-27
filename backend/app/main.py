"""HTTP API. Phase 4 drafts an audit workpaper from a test run."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.config import load_settings
from app.controls.catalog import UnknownControl
from app.controls.runner import fetch_run, list_latest, run_control
from app.database import database_status, get_engine
from app.datasets import DATASETS
from app.load import LoadError, replace_dataset
from app.sampling.service import RunRequired, SampleNotFound, create_sample, get_sample
from app.sampling.select import SamplingError
from app.workpapers.client import AnthropicClient, WorkpaperUnavailable
from app.workpapers.service import (
    WorkpaperClient,
    WorkpaperError,
    WorkpaperLocked,
    WorkpaperNotFound,
    export_markdown,
    generate_workpaper,
    get_workpaper,
    update_workpaper,
)


def create_app(workpaper_client: WorkpaperClient | None = None) -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="The ITAudit System", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.engine = get_engine()
    app.state.workpaper_client = workpaper_client or AnthropicClient()

    @app.get("/health")
    def health() -> dict[str, str]:
        status = database_status(app.state.engine)
        return {"status": "ok" if status == "up" else "degraded", "database": status}

    @app.get("/api/v1/meta")
    def meta() -> dict[str, object]:
        return {"name": "The ITAudit System", "phase": 4, "datasets": list(DATASETS)}

    @app.post("/api/upload/{dataset}")
    async def upload_dataset(dataset: str, request: Request) -> JSONResponse:
        if dataset not in DATASETS:
            known = ", ".join(DATASETS)
            return JSONResponse(
                status_code=404,
                content={"detail": f"Unknown dataset {dataset}. Expected one of: {known}"},
            )
        raw = await request.body()
        try:
            csv_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LoadError("CSV must be UTF-8") from exc
        loaded = replace_dataset(app.state.engine, dataset, csv_text)
        return JSONResponse(content={"dataset": dataset, "rows": loaded})

    @app.post("/api/tests/{control_id}/run")
    def run_test(control_id: str) -> dict[str, object]:
        return run_control(app.state.engine, control_id)

    @app.get("/api/tests")
    def list_tests() -> dict[str, object]:
        return {"runs": list_latest(app.state.engine)}

    @app.get("/api/tests/{control_id}/runs/{run_id}")
    def read_run(control_id: str, run_id: int) -> dict[str, object]:
        return fetch_run(app.state.engine, control_id, run_id)

    @app.post("/api/tests/{control_id}/sample")
    def sample_population(control_id: str, body: SampleRequest) -> dict[str, object]:
        return create_sample(
            app.state.engine,
            control_id,
            body.method,
            body.sample_size,
            body.seed,
        )

    @app.get("/api/samples/{sample_id}")
    def read_sample(sample_id: int) -> dict[str, object]:
        return get_sample(app.state.engine, sample_id)

    @app.post("/api/workpapers/generate")
    def generate(body: WorkpaperRequest) -> dict[str, object]:
        return generate_workpaper(
            app.state.engine,
            app.state.workpaper_client,
            body.control_id,
            body.run_id,
            body.sample_id,
        )

    @app.get("/api/workpapers/{workpaper_id}")
    def read_workpaper(workpaper_id: int) -> dict[str, object]:
        return get_workpaper(app.state.engine, workpaper_id)

    @app.patch("/api/workpapers/{workpaper_id}")
    def patch_workpaper(workpaper_id: int, body: WorkpaperPatch) -> dict[str, object]:
        return update_workpaper(
            app.state.engine,
            workpaper_id,
            body.sections,
            body.status,
            body.reviewer_notes,
        )

    @app.get("/api/workpapers/{workpaper_id}/export")
    def export_workpaper(workpaper_id: int) -> Response:
        return Response(
            content=export_markdown(app.state.engine, workpaper_id),
            media_type="text/markdown",
        )

    @app.exception_handler(WorkpaperLocked)
    async def workpaper_locked(_request: Request, exc: WorkpaperLocked) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(WorkpaperError)
    async def workpaper_error(_request: Request, exc: WorkpaperError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(WorkpaperNotFound)
    async def workpaper_missing(_request: Request, exc: WorkpaperNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(WorkpaperUnavailable)
    async def workpaper_unavailable(_request: Request, exc: WorkpaperUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(SamplingError)
    async def sampling_error(_request: Request, exc: SamplingError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RunRequired)
    async def run_required(_request: Request, exc: RunRequired) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SampleNotFound)
    async def sample_missing(_request: Request, exc: SampleNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UnknownControl)
    async def unknown_control(_request: Request, exc: UnknownControl) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(LoadError)
    async def load_error(_request: Request, exc: LoadError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


class WorkpaperRequest(BaseModel):
    control_id: str
    run_id: int
    sample_id: int | None = None


class WorkpaperPatch(BaseModel):
    sections: dict[str, str] | None = None
    status: Literal["draft", "reviewed", "approved"] | None = None
    reviewer_notes: str | None = None


class SampleRequest(BaseModel):
    method: Literal["random", "risk_based"]
    sample_size: int = Field(ge=1)
    seed: int | None = None


app = create_app()
