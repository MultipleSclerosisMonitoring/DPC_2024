from pydantic import BaseModel, Field
from typing import Optional, List


class CodeID(BaseModel):
    codeid: str  # El CodeID único
    id: Optional[int] = Field(default=None)  # Solo se usa si ya existe en la base de datos


class ActivityLeg(BaseModel):
    codeid_id: int  # Relación con la tabla codeids
    foot: str  # "Left" o "Right"
    start_time: str  # ISO 8601 timestamp
    end_time: str  # ISO 8601 timestamp
    duration: float  # Duración en segundos
    total_value: float # Sample number collected
    mac: Optional[str] = None
    device_name: Optional[str] = None
    total_value: float

class ActivityAll(BaseModel):
    codeid_ids: List[int] = []  # Relación con la tabla codeids Right and Left
    codeleg_ids: List[int] = [] # Pair of pointers to the activity_leg ID
    start_time: str  # ISO 8601 timestamp
    end_time: str  # ISO 8601 timestamp
    duration: float  # Duración del período sincronizado
    # total_value: List[float] # Number of samples per leg linked active_legs Such info is not available
    macs: List[str] = []  # list of Right amd Left macs
    active_legs: List[str] = []  # Almacena las piernas activas, e.g., ["Right", "Left"]
    device_names: List[str] = [] # Store devices 
    is_effective: Optional[bool] = Field(default=False)  # Indica si es una marcha efectiva

