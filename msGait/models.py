from pydantic import BaseModel


class EffectiveMovement(BaseModel):
    codeid_id: int
    start_time: str
    end_time: str
    duration: float
    leg: str


class EffectiveGait(BaseModel):
    codeid_id: int
    start_time: str
    end_time: str
    duration: float
    gait_confidence_level: int
    gps_points: int | None = None
    gps_distance_m: float | None = None
    gps_elapsed_sec: float | None = None
    gps_avg_speed_m_s: float | None = None
    gps_validated: bool | None = None


class ActivitySegment(BaseModel):
    codeid_id: int
    foot: str
    device_name: str | None = None
    mac: str | None = None
    start_time: str
    end_time: str