from pydantic import BaseModel, Field


class CodeID(BaseModel):
    codeid: str
    id: int | None = Field(default=None)


class ActivityLeg(BaseModel):
    codeid_id: int
    foot: str
    start_time: str
    end_time: str
    duration: float
    total_value: float
    mac: str | None = None
    device_name: str | None = None


class ActivityAll(BaseModel):
    codeid_ids: list[int] = Field(default_factory=list)
    codeleg_ids: list[int] = Field(default_factory=list)
    start_time: str
    end_time: str
    duration: float
    macs: list[str] = Field(default_factory=list)
    active_legs: list[str] = Field(default_factory=list)
    device_names: list[str] = Field(default_factory=list)
    is_effective: bool = Field(default=False)