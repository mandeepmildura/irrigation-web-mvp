from __future__ import annotations

import logging
import atexit
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from db import (
    Base,
    engine,
    get_db,
    SessionLocal,
    ensure_sqlite_schema,
)
import models, schemas

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("irrigation")

app = FastAPI(title="Irrigation Web MVP")

# -------------------- CORS --------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_READY = True

# -------------------- Health --------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "ts": datetime.utcnow().isoformat(),
        "db_ready": DB_READY,
    }


@app.get("/now")
def now_time():
    mel = datetime.now(ZoneInfo("Australia/Melbourne"))
    utc = datetime.utcnow()
    return {
        "melbourne": mel.strftime("%Y-%m-%d %H:%M:%S"),
        "utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
    }


# -------------------- Helpers --------------------
def execute_run(db: Session, zone_name: str, minutes: int, source: str):
    r = models.IrrigationRun(
        zone_name=zone_name,
        duration_minutes=minutes,
        source=source,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


# -------------------- Zones --------------------
@app.post("/zones", response_model=schemas.ZoneOut)
def create_zone(payload: schemas.ZoneCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Zone).filter(models.Zone.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Zone already exists")

    z = models.Zone(
        name=payload.name,
        description=payload.description or "",
    )
    db.add(z)
    db.commit()
    db.refresh(z)
    return z


@app.get("/zones", response_model=list[schemas.ZoneOut])
def list_zones(db: Session = Depends(get_db)):
    return db.query(models.Zone).order_by(models.Zone.id).all()


# -------------------- Schedules --------------------
@app.post("/schedules", response_model=schemas.ScheduleOut)
def create_schedule(payload: schemas.ScheduleCreate, db: Session = Depends(get_db)):
    zone = db.query(models.Zone).filter(models.Zone.id == payload.zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    s = models.Schedule(
        zone_id=payload.zone_id,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
        enabled=1 if payload.enabled else 0,
        days_of_week=payload.days_of_week or "*",
        skip_if_moisture_over=payload.skip_if_moisture_over,
        moisture_lookback_minutes=payload.moisture_lookback_minutes,
        last_run_minute=None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.get("/schedules", response_model=list[schemas.ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).order_by(models.Schedule.id).all()


# -------------------- Manual run --------------------
@app.post("/run/{zone_name}", response_model=schemas.RunOut)
def run_zone(zone_name: str, minutes: int = 10, source: str = "manual"):
    db = SessionLocal()
    try:
        return execute_run(db, zone_name, minutes, source)
    finally:
        db.close()


# -------------------- Run history --------------------
@app.get("/runs", response_model=list[schemas.RunOut])
def list_runs(limit: int = 100, zone_name: str | None = None):
    db = SessionLocal()
    try:
        q = db.query(models.IrrigationRun)
        if zone_name:
            q = q.filter(models.IrrigationRun.zone_name == zone_name)
        return q.order_by(models.IrrigationRun.ts.desc()).limit(limit).all()
    finally:
        db.close()


# -------------------- Sensor readings --------------------
@app.post("/readings", response_model=schemas.SensorReadingOut)
def add_reading(payload: schemas.SensorReadingCreate, db: Session = Depends(get_db)):
    r = models.SensorReading(
        zone_name=payload.zone_name,
        metric=payload.metric,
        value=payload.value,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@app.get("/readings", response_model=list[schemas.SensorReadingOut])
def latest_readings(limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(models.SensorReading)
        .order_by(models.SensorReading.ts.desc())
        .limit(limit)
        .all()
    )


# -------------------- Charts (THIS FIXES THE BLANK GRAPH) --------------------
@app.get("/chart/series")
def chart_series(
    zone_name: str,
    metric: str,
    hours: int = 24,
):
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)

        rows = (
            db.query(models.SensorReading)
            .filter(models.SensorReading.zone_name == zone_name)
            .filter(models.SensorReading.metric == metric)
            .filter(models.SensorReading.ts >= since)
            .order_by(models.SensorReading.ts.asc())
            .all()
        )

        return {
            "labels": [r.ts.strftime("%H:%M") for r in rows],
            "values": [r.value for r in rows],
        }
    finally:
        db.close()


# -------------------- Scheduler --------------------
scheduler = BackgroundScheduler(timezone="Australia/Melbourne")


def schedule_tick():
    if not DB_READY:
        return

    mel_now = datetime.now(ZoneInfo("Australia/Melbourne"))
    current_minute = mel_now.strftime("%H:%M")

    db = SessionLocal()
    try:
        schedules = db.query(models.Schedule).filter(models.Schedule.enabled == 1).all()

        for s in schedules:
            if s.start_time == current_minute and s.last_run_minute != current_minute:
                zone = db.query(models.Zone).filter(models.Zone.id == s.zone_id).first()
                if zone:
                    execute_run(
                        db,
                        zone.name,
                        s.duration_minutes,
                        f"schedule:{s.id}",
                    )
                    s.last_run_minute = current_minute
                    db.commit()
    finally:
        db.close()


@app.on_event("startup")
def startup():
    global DB_READY

    try:
        ensure_sqlite_schema()
        Base.metadata.create_all(bind=engine)
        DB_READY = True
        log.info("DB ready")
    except Exception as e:
        DB_READY = False
        log.exception("DB init failed: %s", e)
        return

    if not scheduler.running:
        scheduler.add_job(schedule_tick, "interval", seconds=20, id="schedule_tick")
        scheduler.start()
        log.info("Scheduler started")


atexit.register(lambda: scheduler.shutdown(wait=False))


# -------------------- Dashboard --------------------
FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@app.get("/")
def dashboard():
    return FileResponse(str(FRONTEND_INDEX))
