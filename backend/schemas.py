from pydantic import BaseModel, validator
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
    days_of_week: str = "*"
    skip_if_moisture_over: float | None = None
    moisture_lookback_minutes: int = 120

    @validator("start_time")
    def validate_start_time(cls, v: str) -> str:
        if len(v) != 5 or v[2] != ":":
            raise ValueError("start_time must be HH:MM")
        hour, minute = v.split(":")
        if not hour.isdigit() or not minute.isdigit():
            raise ValueError("start_time must be numeric HH:MM")
        h, m = int(hour), int(minute)
        if h < 0 or h > 23 or m < 0 or m > 59:
            raise ValueError("start_time must be a valid 24h time")
        return f"{h:02d}:{m:02d}"

    @validator("duration_minutes")
    def validate_duration(cls, v: int) -> int:
        if v < 1 or v > 240:
            raise ValueError("duration_minutes must be between 1 and 240")
        return v

    @validator("days_of_week")
    def normalize_days(cls, v: str) -> str:
        if v.strip() == "*":
            return "*"
        allowed = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        days = [d.strip().lower() for d in v.split(",") if d.strip()]
        if not days:
            raise ValueError("days_of_week must not be empty")
        unknown = [d for d in days if d not in allowed]
        if unknown:
            raise ValueError(f"Unsupported day values: {', '.join(unknown)}")
        return ",".join(sorted(set(days)))

    @validator("moisture_lookback_minutes")
    def validate_lookback(cls, v: int) -> int:
        if v < 15 or v > 1440:
            raise ValueError("moisture_lookback_minutes must be between 15 and 1440")
        return v

class ScheduleOut(BaseModel):
    id: int
    zone_id: int
    start_time: str
    duration_minutes: int
    enabled: int
    days_of_week: str
    skip_if_moisture_over: float | None
    moisture_lookback_minutes: int
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
