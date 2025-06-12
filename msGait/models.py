from pydantic import BaseModel, Field
from typing import Optional, List


class EffectiveMovement(BaseModel):
    codeid_id: int  # Relación con la tabla codeids
    start_time: str  # ISO 8601 timestamp
    end_time: str  # ISO 8601 timestamp
    duration: float
    leg: str  # "Left" o "Right"


class ActivitySegment(BaseModel):
    codeid_id: int
    foot: str  # "Left" o "Right"
    device_name: Optional[str] = None
    mac: Optional[str] = None
    start_time: str  # ISO 8601 timestamp
    end_time: str  # ISO 8601 timestamp
