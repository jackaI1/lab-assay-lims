"""Local-only FastAPI service and its single-page bench workflow."""

import csv
import io
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Header, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .analysis import analyse
from .demo import seed_demo, synthetic_plate
from .importers import MAX_BYTES, parse_reader, well_name
from .protocols import plate_transfer, serial_dilution
from .store import Store

STATIC = Path(__file__).parent / "static"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Sample(Input):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    description: str = Field(min_length=1, max_length=500)


class Lot(Input):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    reagent: str = Field(min_length=1, max_length=200)
    expires_on: date


class Well(Input):
    well: str
    role: Literal["blank", "standard", "positive", "negative", "sample"]
    sample_id: str | None = Field(default=None, min_length=1, max_length=80)
    concentration: float | None = Field(default=None, ge=0, le=1e12)
    dilution_factor: float = Field(default=1, ge=1, le=1e6)

    @field_validator("well")
    @classmethod
    def address(cls, value):
        return well_name(value)

    @model_validator(mode="after")
    def relationships(self):
        if (self.role == "sample") != (self.sample_id is not None):
            raise ValueError("Only sample wells require a registered sample ID")
        if (self.role == "standard") != (self.concentration is not None):
            raise ValueError("Only standard wells require a known concentration")
        if self.role != "sample" and self.dilution_factor != 1:
            raise ValueError("Dilution correction applies only to sample wells")
        return self


class Plate(Input):
    name: str = Field(min_length=1, max_length=120)
    lot_id: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="ng/mL", min_length=1, max_length=30)
    wells: list[Well] = Field(min_length=1, max_length=96)

    @model_validator(mode="after")
    def unique_wells(self):
        if len({w.well for w in self.wells}) != len(self.wells):
            raise ValueError("Plate map contains duplicate wells")
        return self


class AnalysisRequest(Input):
    model: Literal["linear", "4pl"] = "4pl"


class Move(Input):
    source: str
    destination: str
    volume: float


class ProtocolRequest(Input):
    kind: Literal["serial", "transfer"]
    steps: int = 8
    factor: float = 2
    final_volume: float = 80
    row: str = "A"
    moves: list[Move] = Field(default_factory=list, max_length=96)
    source_volumes: dict[str, float] = Field(default_factory=dict)


def create_app(db_path=None):
    app = FastAPI(title="Lab assay notebook", version="0.1.0", docs_url=None, redoc_url=None)
    store = Store(db_path or os.environ.get("LIMS_DB", "assays.sqlite"))
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method not in ["GET", "HEAD", "OPTIONS"]
            and origin
            and origin != str(request.base_url).rstrip("/")
        ):
            return JSONResponse(
                status_code=403, content={"detail": "Use the local app page to change records"}
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc).strip("'")})

    @app.exception_handler(sqlite3.IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(
            status_code=409,
            content={"detail": "Record already exists; records are immutable. Use a new ID or plate name."},
        )

    def actor(value):
        if not value or len(value) > 80 or any(ord(c) < 32 for c in value):
            raise ValueError("Actor must contain 1 to 80 printable characters")
        return value

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/docs", include_in_schema=False)
    def docs():
        return FileResponse(STATIC / "api.html")

    @app.get("/api/samples")
    def samples():
        return store.list_records("samples")

    @app.post("/api/samples", status_code=201)
    def add_sample(data: Sample, x_actor: str = Header(default="local-user")):
        return store.create_sample(data.model_dump(), actor(x_actor))

    @app.get("/api/lots")
    def lots():
        return store.list_records("lots")

    @app.post("/api/lots", status_code=201)
    def add_lot(data: Lot, x_actor: str = Header(default="local-user")):
        return store.create_lot(data.model_dump(mode="json"), actor(x_actor))

    @app.get("/api/plates")
    def plates():
        return store.list_records("plates")

    @app.post("/api/plates", status_code=201)
    def add_plate(data: Plate, x_actor: str = Header(default="local-user")):
        return store.create_plate(data.model_dump(exclude_none=True), actor(x_actor))

    @app.get("/api/plates/{plate_id}")
    def plate(plate_id: int):
        return store.get_plate(plate_id)

    @app.post("/api/plates/{plate_id}/imports", status_code=201)
    async def import_reader(
        plate_id: int, file: UploadFile = File(), x_actor: str = Header(default="local-user")
    ):
        try:
            content = await file.read(MAX_BYTES + 1)
        finally:
            await file.close()
        signals = parse_reader(file.filename or "", content)
        return store.add_import(plate_id, file.filename or "reader.csv", content, signals, actor(x_actor))

    @app.get("/api/imports/{import_id}/file")
    def original(import_id: int):
        data = store.get_import(import_id)
        media = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if data["name"].lower().endswith(".xlsx")
            else "text/csv"
        )
        return Response(
            data["content"],
            media_type=media,
            headers={
                "Content-Disposition": 'attachment; filename="reader-export'
                + (".xlsx" if media != "text/csv" else ".csv")
                + '"'
            },
        )

    @app.post("/api/imports/{import_id}/analyses", status_code=201)
    def run_analysis(import_id: int, data: AnalysisRequest, x_actor: str = Header(default="local-user")):
        imported = store.get_import(import_id)
        plate = store.get_plate(imported["plate_id"])
        result = analyse(plate["wells"], imported["signals"], data.model)
        result["unit"] = plate["unit"]
        result["reagent_lot"] = plate["lot"]
        result["source_sha256"] = imported["sha256"]
        result["analysed_on"] = str(date.today())
        if date.fromisoformat(plate["lot"]["expires_on"]) < date.today():
            result["flags"].append("EXPIRED_REAGENT_LOT")
            result["passed"] = False
        return store.save_analysis(import_id, data.model, result, actor(x_actor))

    @app.get("/api/analyses/{analysis_id}")
    def analysis(analysis_id: int):
        return store.get_analysis(analysis_id)

    @app.get("/api/analyses/{analysis_id}/csv")
    def analysis_csv(analysis_id: int):
        analysis = store.get_analysis(analysis_id)
        imported = store.get_import(analysis["import_id"])
        plate = store.get_plate(imported["plate_id"])
        mapping = {w["well"]: w for w in plate["wells"]}
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "well",
                "role",
                "sample_id",
                "raw",
                "blank_corrected",
                "concentration",
                "unit",
                "well_flags",
                "group_flags",
                "plate_flags",
                "plate_passed",
                "analysis_id",
                "source_sha256",
            ]
        )
        group_flags = {w: g["flags"] for g in analysis["result"]["groups"] for w in g["wells"]}
        for well, values in analysis["result"]["wells"].items():
            writer.writerow(
                [
                    well,
                    mapping[well]["role"],
                    mapping[well].get("sample_id", ""),
                    values["raw"],
                    values["corrected"],
                    values["concentration"],
                    plate["unit"],
                    ";".join(values["flags"]),
                    ";".join(group_flags[well]),
                    ";".join(analysis["result"]["flags"]),
                    analysis["result"]["passed"],
                    analysis_id,
                    imported["sha256"],
                ]
            )
        return Response(
            out.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="assay-results.csv"'},
        )

    @app.post("/api/plates/{plate_id}/protocols", status_code=201)
    def protocol(plate_id: int, data: ProtocolRequest, x_actor: str = Header(default="local-user")):
        store.get_plate(plate_id)
        if data.kind == "serial":
            source, plan = serial_dilution(data.steps, data.factor, data.final_volume, data.row)
        else:
            source, plan = plate_transfer([m.model_dump() for m in data.moves], data.source_volumes)
        saved = store.save_protocol(plate_id, data.kind, data.model_dump(), source, actor(x_actor))
        return dict(
            **saved, plan=plan, simulation_status="not run; run opentrons_simulate on this exported file"
        )

    @app.get("/api/protocols/{protocol_id}/file")
    def protocol_file(protocol_id: int):
        saved = store.get_protocol(protocol_id)
        return Response(
            saved["source"],
            media_type="text/x-python",
            headers={"Content-Disposition": 'attachment; filename="assay-protocol.py"'},
        )

    @app.get("/api/audit")
    def audit():
        return store.list_records("audit")

    @app.post("/api/demo")
    def demo(x_actor: str = Header(default="local-user")):
        result, created = seed_demo(store, actor(x_actor))
        return JSONResponse(result, status_code=201 if created else 200)

    @app.get("/api/templates/synthetic-reader.csv")
    def demo_reader():
        return Response(
            synthetic_plate()[1],
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="synthetic-reader.csv"'},
        )

    @app.get("/api/templates/synthetic-map")
    def demo_map():
        return synthetic_plate()[0]

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
