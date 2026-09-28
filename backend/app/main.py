"""HTTP API. Phase 5 serves the audit dashboard."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.audit_context import DatasetError, RealDataDisabled, activate, allow_real_data, data_source, load_rules, require_real_data, save_rules, saved_mapping
from app.completeness import completeness_report
from app.config import load_settings
from app.controls.catalog import UnknownControl, describe_controls
from app.controls.runner import fetch_run, list_latest, run_all, run_control
from app.controls.severity import annotate_run
from app.database import database_status, get_engine
from app.datasets import DATASETS
from app.importer import IMPORT_DATASETS, commit_import, inspect_csv, template_csv, validate_bundle
from app.load import LoadError, replace_dataset
from app.overview import build_overview, dataset_counts
from app.sampling.service import RunRequired, SampleNotFound, create_sample, get_sample, latest_sample
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
    list_workpapers,
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
        return {"name": "The ITAudit System", "phase": 5, "datasets": list(DATASETS)}

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

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        return build_overview(app.state.engine)

    @app.get("/api/controls")
    def controls() -> dict[str, object]:
        return {"controls": describe_controls()}

    @app.get("/api/datasets")
    def datasets() -> dict[str, object]:
        return {"datasets": dataset_counts(app.state.engine)}

    @app.get("/api/data-source")
    def read_data_source() -> dict[str, object]:
        return data_source(app.state.engine)

    @app.post("/api/data-source")
    def choose_data_source(body: DataSourceRequest) -> dict[str, object]:
        return activate(app.state.engine, body.dataset)

    @app.get("/api/settings")
    def read_settings() -> dict[str, object]:
        rules = load_rules(app.state.engine)
        rules["allow_real_data"] = allow_real_data()
        return rules

    @app.put("/api/settings")
    def write_settings(body: RulesRequest) -> dict[str, object]:
        return save_rules(app.state.engine, body.model_dump())

    @app.get("/api/completeness")
    def read_completeness() -> dict[str, object]:
        source = data_source(app.state.engine)
        return {"dataset": source["dataset"], "label": source["label"], "controls": completeness_report(app.state.engine)}

    @app.get("/api/import/templates/{dataset}")
    def import_template(dataset: str) -> Response:
        require_real_data()
        if dataset not in IMPORT_DATASETS:
            return JSONResponse(status_code=404, content={"detail": f"Unknown import {dataset}."})
        return Response(
            content=template_csv(dataset),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{dataset}.csv"'},
        )

    @app.post("/api/import/inspect")
    def import_inspect(body: InspectRequest) -> dict[str, object]:
        require_real_data()
        saved = saved_mapping(app.state.engine, body.dataset)
        if body.mapping is not None:
            saved = {
                "mapping": body.mapping,
                "status_map": body.status_map or (saved or {}).get("status_map", {}),
            }
        return inspect_csv(body.dataset, body.csv, saved)

    @app.post("/api/import/validate")
    def import_validate(body: ImportBundle) -> dict[str, object]:
        require_real_data()
        report = validate_bundle(_files(body))
        report.pop("rows", None)
        return report

    @app.post("/api/import/commit")
    def import_commit(body: ImportBundle) -> dict[str, object]:
        return commit_import(app.state.engine, _files(body))

    @app.post("/api/tests/run-all")
    def run_every_test() -> dict[str, object]:
        return {"runs": [annotate_run(run) for run in run_all(app.state.engine)]}

    @app.post("/api/tests/{control_id}/run")
    def run_test(control_id: str) -> dict[str, object]:
        return annotate_run(run_control(app.state.engine, control_id))

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

    @app.get("/api/tests/{control_id}/sample")
    def read_latest_sample(control_id: str) -> dict[str, object]:
        return latest_sample(app.state.engine, control_id)

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

    @app.get("/api/workpapers")
    def read_workpapers() -> dict[str, object]:
        return {"workpapers": list_workpapers(app.state.engine)}

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

    @app.exception_handler(DatasetError)
    async def dataset_error(_request: Request, exc: DatasetError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RealDataDisabled)
    async def real_data_disabled(_request: Request, exc: RealDataDisabled) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

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


class DataSourceRequest(BaseModel):
    dataset: str


class RulesRequest(BaseModel):
    dormant_days: int
    privileged_roles: list[str]
    critical_systems: list[str]
    sod_pairs: list[dict[str, str]]


class InspectRequest(BaseModel):
    dataset: str
    csv: str
    mapping: dict[str, str] | None = None
    status_map: dict[str, str] | None = None


class ImportFile(BaseModel):
    csv: str
    mapping: dict[str, str] = Field(default_factory=dict)
    status_map: dict[str, str] = Field(default_factory=dict)


class ImportBundle(BaseModel):
    files: dict[str, ImportFile]


def _files(body: ImportBundle) -> dict[str, dict[str, object]]:
    return {
        name: {"csv": item.csv, "mapping": item.mapping, "status_map": item.status_map}
        for name, item in body.files.items()
    }


app = create_app()
