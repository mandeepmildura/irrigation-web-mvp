from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base

class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    description: Mapped[str] = mapped_column(String, default="")

    schedules = relationship("Schedule", back_populates="zone", cascade="all, delete-orphan")

class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    start_time: Mapped[str] = mapped_column(String)  # "HH:MM"
    duration_minutes: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    last_run_minute: Mapped[str | None] = mapped_column(String, nullable=True)
  
    zone = relationship("Zone", back_populates="schedules")

class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    zone_name: Mapped[str] = mapped_column(String, index=True)
    metric: Mapped[str] = mapped_column(String, index=True)  # e.g. "soil_moisture"
    value: Mapped[float] = mapped_column(Float)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class IrrigationRun(Base):
    __tablename__ = "irrigation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    zone_name: Mapped[str] = mapped_column(String, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, index=True)  # "manual" or "schedule:<id>"
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
