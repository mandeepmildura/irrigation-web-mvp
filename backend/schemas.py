from datetime import datetime
from pydantic import BaseModel, Field


# ---------- Zones ----------
class ZoneCreate(BaseModel):
    name: str
    description: str | None = ""


class ZoneOut(BaseModel):
    id: int
    name: str
    description: str

    model_config = {
        "from_attributes": True
    }


# ---------- Schedules ----------
class ScheduleCreate(BaseModel):
    zone_id: int
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")  # HH:MM
    duration_minutes: int = Field(..., ge=1, le=1440)
    enabled: bool = True

    # irrigation logic
    days_of_week: str = "*"  # "*" or "mon,tue,wed"
    skip_if_moisture_over: float | None = None
    moisture_lookback_minutes: int = Field(default=120, ge=1, le=1440)


class ScheduleOut(BaseModel):
    id: int
    zone_id: int
    start_time: str
    duration_minutes: int
    enabled: int

    days_of_week: str
    skip_if_moisture_over: float | None
    moisture_lookback_minutes: int
    last_run_minute: str | None

    model_config = {
        "from_attributes": True
    }


# ---------- Sensor readings ----------
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

    model_config = {
        "from_attributes": True
    }


# ---------- Irrigation runs ----------
class RunOut(BaseModel):
    id: int
    zone_name: str
    duration_minutes: int
    source: str
    ts: datetime

    model_config = {
        "from_attributes": True
    }
