from pydantic import BaseModel
from datetime import datetime

class ZoneCreate(BaseModel):
    name: str
    description: str = ""

class ZoneOut(BaseModel):
    id: int
    name: str
    description: str
    class Config:
        from_attributes = True

class ScheduleCreate(BaseModel):
    zone_id: int
    start_time: str  # "HH:MM"
    duration_minutes: int
    enabled: bool = True

class ScheduleOut(BaseModel):
    id: int
    zone_id: int
    start_time: str
    duration_minutes: int
    enabled: int
    class Config:
        from_attributes = True

class SensorReadingCreate(BaseModel):
    zone_name: str
    metric: str
    value: float

class SensorReadingOut(BaseModel):
    id: int
    zone_name: str
    metric: str
    value: float
    ts: datetime
    class Config:
        from_attributes = True

class RunOut(BaseModel):
    id: int
    zone_name: str
    duration_minutes: int
    source: str
    ts: datetime
    class Config:
        from_attributes = True
