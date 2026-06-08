from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from msGait.movement_detector import MovementDetector
from msTools.data_manager import DataManager

app = FastAPI(
    title="MS Monitoring API",
    version="0.1.0",
    description="API to display activity windows and gait detection using existing logic.",
    root_path="/msGait",
)

# ---- SINGLETONS ----
_dm: DataManager | None = None
_detector: MovementDetector | None = None


def _default_time_window_utc(hours: int = 24) -> tuple[str, str]:
    """Return (start, end) ISO8601 UTC strings with Z suffix."""
    now = datetime.now(timezone.utc)
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    start = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return start, end


@app.on_event("startup")
def _startup() -> None:
    """Create shared instances when starting the server."""
    global _dm, _detector

    _dm = DataManager(config_path="config.yaml")

    now = datetime.now(timezone.utc)
    fstart = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fend = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    _detector = MovementDetector(
        config_file="config.yaml",
        sect="movement",
        fstart=fstart,
        fend=fend,
        ids=None,
        verbose=0,
    )


# ---- MODELS ----

class GaitRequest(BaseModel):
    ids: list[int]
    save: bool = False
    head_rows: int = 5
    verbose: int = 1
    output_xlsx: str | None = None


class GaitResponse(BaseModel):
    effective_movement_rows: int
    effective_gait_rows: int
    preview_effective_movement: list[dict[str, Any]] = Field(default_factory=list)
    preview_effective_gait: list[dict[str, Any]] = Field(default_factory=list)


# ---- ENDPOINTS ----

@app.get("/")
async def root(request: Request) -> RedirectResponse:
    return RedirectResponse(url=request.url_for("swagger_ui_html"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/codeids", response_model=list[str])
def list_codeids(
    start: str | None = Query(None, description="YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(None, description="YYYY-MM-DD HH:MM:SS"),
) -> list[str]:
    """
    Return the list of CodeIDs in an optional range.
    Internally uses DataManager.get_codeids_in_range(start, end).
    """
    if _dm is None:
        raise HTTPException(status_code=500, detail="DataManager not initialized")

    try:
        if start is None or end is None:
            start, end = _default_time_window_utc(hours=24)
        return _dm.get_codeids_in_range(start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving codeids: {e}")


@app.get("/activity-windows")
def activity_windows(
    start: str | None = Query(None, description="YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(None, description="YYYY-MM-DD HH:MM:SS"),
    ids: list[int] | None = Query(None, description="activity_all IDs (repeat ?ids=x)"),
    verbose: int = 0,
) -> list[dict[str, Any]]:
    """
    Return activity windows from activity_all.
    Internally uses DataManager.segments_retrieval(fstart, fend, ids, verbose).
    """
    if _dm is None:
        raise HTTPException(status_code=500, detail="DataManager not initialized")

    try:
        if ids is None and (start is None or end is None):
            start, end = _default_time_window_utc(hours=24)

        df = _dm.segments_retrieval(
            fstart=start,
            fend=end,
            ids=ids,
            verbose=verbose,
        )
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving activity windows: {e}")


@app.get("/sensor-data")
def sensor_data(
    codeid_id: int,
    foot: Literal["Left", "Right"],
    start: str = Query(..., description="YYYY-MM-DD HH:MM:SS"),
    end: str = Query(..., description="YYYY-MM-DD HH:MM:SS"),
) -> list[dict[str, Any]]:
    """
    Return raw sensor data for a codeid/foot in a range.
    Internally uses MovementDetector.fetch_sensor_data(start, end, codeid_id, foot).
    """
    if _detector is None:
        raise HTTPException(status_code=500, detail="MovementDetector not initialized")

    try:
        df = _detector.fetch_sensor_data(start, end, codeid_id, foot)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sensor data: {e}")


@app.post("/gait/detect", response_model=GaitResponse)
def detect_gait(req: GaitRequest) -> GaitResponse:
    """
    Run the detection pipeline on a list of activity_all IDs:
    - detect_effective_movement
    - detect_effective_gait
    - validate_gait_with_gps
    - optional save in PostgreSQL
    """
    if _dm is None or _detector is None:
        raise HTTPException(status_code=500, detail="API dependencies not initialized")

    try:
        # 1) Base windows from activity_all by IDs
        base_windows = _dm.segments_retrieval(
            fstart=None,
            fend=None,
            ids=req.ids,
            verbose=req.verbose,
        )

        # 2) Transform into rows by leg
        df_legs = _dm.recover_activity_all(base_windows, verbose=req.verbose)

        # 3) Effective movement
        df_eff = _detector.detect_effective_movement(
            activity_windows=df_legs,
            output_filename=req.output_xlsx,
            verbose=req.verbose,
        )

        # 4) Gait + GPS validation
        df_gait = _detector.detect_effective_gait(df_eff, verbose=req.verbose)
        df_gait = _detector.validate_gait_with_gps(df_gait, verbose=req.verbose)

        # 5) Optional storage
        if req.save:
            _detector.save_to_postgresql("effective_movement", df_eff, verbose=req.verbose)
            _detector.save_to_postgresql("effective_gait", df_gait, verbose=req.verbose)

        # 6) Response
        return GaitResponse(
            effective_movement_rows=len(df_eff),
            effective_gait_rows=len(df_gait),
            preview_effective_movement=df_eff.head(req.head_rows).to_dict(orient="records"),
            preview_effective_gait=df_gait.head(req.head_rows).to_dict(orient="records"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gait detection failed: {e}")


@app.on_event("shutdown")
def _shutdown() -> None:
    global _dm, _detector

    if _detector is not None:
        _detector.close()
        _detector = None

    if _dm is not None:
        _dm.close_all()
        _dm = None