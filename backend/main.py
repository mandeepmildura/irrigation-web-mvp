import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import atexit

from alembic import command
from alembic.config import Config

from db import DATABASE_URL, USING_SQLITE_FALLBACK, get_db, SessionLocal
import models, schemas

API_TOKEN = os.getenv("API_TOKEN")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(title="Irrigation Web MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parent / "alembic.ini"


def run_migrations():
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.set_main_option(
        "script_location", str((Path(__file__).resolve().parent / "alembic").resolve())
    )
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    if USING_SQLITE_FALLBACK:
        print("[db] Warning: DATABASE_URL not set; using local SQLite fallback for development.")
    print("[db] Starting migrations...")
    command.upgrade(config, "head")
    print("[db] Migrations applied successfully.")


def require_api_key(api_key: str | None = Security(api_key_header)):
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="API token not configured")
    if api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key

@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat()}

@app.get("/now")
def now_time():
    mel = datetime.now(ZoneInfo("Australia/Melbourne"))
    utc = datetime.utcnow()
    return {
        "melbourne": mel.strftime("%Y-%m-%d %H:%M:%S"),
        "utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
    }

# ---------- Run logging helper ----------
def execute_run(zone_name: str, minutes: int, source: str):
    db = SessionLocal()
    try:
        r = models.IrrigationRun(zone_name=zone_name, duration_minutes=minutes, source=source)
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    finally:
        db.close()

# ---------- Zones ----------
@app.post("/zones", response_model=schemas.ZoneOut)
def create_zone(
    payload: schemas.ZoneCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    existing = db.query(models.Zone).filter(models.Zone.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Zone name already exists")
    z = models.Zone(name=payload.name, description=payload.description)
    db.add(z)
    db.commit()
    db.refresh(z)
    return z

@app.get("/zones", response_model=list[schemas.ZoneOut])
def list_zones(db: Session = Depends(get_db), api_key: str = Depends(require_api_key)):
    return db.query(models.Zone).order_by(models.Zone.id).all()

# ---------- Schedules ----------
@app.post("/schedules", response_model=schemas.ScheduleOut)
def create_schedule(
    payload: schemas.ScheduleCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    zone = db.query(models.Zone).filter(models.Zone.id == payload.zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    s = models.Schedule(
        zone_id=payload.zone_id,
        start_time=payload.start_time,
        duration_minutes=payload.duration_minutes,
        enabled=1 if payload.enabled else 0,
        days_of_week=payload.days_of_week,
        skip_if_moisture_over=payload.skip_if_moisture_over,
        moisture_lookback_minutes=payload.moisture_lookback_minutes,
        last_run_minute=None,  # new
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/schedules", response_model=list[schemas.ScheduleOut])
def list_schedules(db: Session = Depends(get_db), api_key: str = Depends(require_api_key)):
    return db.query(models.Schedule).order_by(models.Schedule.id).all()

# ---------- Manual run (logs to DB) ----------
@app.post("/run/{zone_name}", response_model=schemas.RunOut)
def run_zone(
    zone_name: str,
    minutes: int = 10,
    source: str = "manual",
    api_key: str = Depends(require_api_key),
):
    return execute_run(zone_name=zone_name, minutes=minutes, source=source)

# ---------- Run history ----------
@app.get("/runs", response_model=list[schemas.RunOut])
def list_runs(limit: int = 100, zone_name: str | None = None, api_key: str = Depends(require_api_key)):
    db = SessionLocal()
    try:
        q = db.query(models.IrrigationRun)
        if zone_name:
            q = q.filter(models.IrrigationRun.zone_name == zone_name)
        return q.order_by(models.IrrigationRun.ts.desc()).limit(limit).all()
    finally:
        db.close()

# ---------- Sensors ----------
@app.post("/readings", response_model=schemas.SensorReadingOut)
def add_reading(
    payload: schemas.SensorReadingCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    r = models.SensorReading(zone_name=payload.zone_name, metric=payload.metric, value=payload.value)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

@app.get("/readings", response_model=list[schemas.SensorReadingOut])
def latest_readings(
    limit: int = 50,
    db: Session = Depends(get_db),
    api_key: str = Depends(require_api_key),
):
    return (
        db.query(models.SensorReading)
        .order_by(models.SensorReading.ts.desc())
        .limit(limit)
        .all()
    )


# ---------- Scheduler (skip missed; never double-run within same minute) ----------
scheduler = BackgroundScheduler(timezone="Australia/Melbourne")

def _is_day_allowed(schedule: models.Schedule, mel_now: datetime) -> bool:
    if schedule.days_of_week == "*":
        return True
    allowed = set(schedule.days_of_week.split(","))
    today = mel_now.strftime("%a").lower()[:3]
    return today in allowed


def _should_skip_for_moisture(schedule: models.Schedule, zone_name: str, db: Session) -> bool:
    if schedule.skip_if_moisture_over is None:
        return False
    lookback_start = datetime.utcnow() - timedelta(minutes=schedule.moisture_lookback_minutes)
    latest = (
        db.query(models.SensorReading)
        .filter(models.SensorReading.zone_name == zone_name)
        .filter(models.SensorReading.metric == "moisture")
        .filter(models.SensorReading.ts >= lookback_start)
        .order_by(models.SensorReading.ts.desc())
        .first()
    )
    if not latest:
        return False
    return latest.value >= schedule.skip_if_moisture_over


def schedule_tick():
    mel_now = datetime.now(ZoneInfo("Australia/Melbourne"))
    current_minute = mel_now.strftime("%H:%M")

    db = SessionLocal()
    try:
        schedules = db.query(models.Schedule).filter(models.Schedule.enabled == 1).all()

        for s in schedules:
            # run once per matching minute
            if s.start_time == current_minute and s.last_run_minute != current_minute:
                if not _is_day_allowed(s, mel_now):
                    continue
                zone = db.query(models.Zone).filter(models.Zone.id == s.zone_id).first()
                if zone:
                    if _should_skip_for_moisture(s, zone.name, db):
                        s.last_run_minute = current_minute
                        db.commit()
                        continue
                    execute_run(
                        zone_name=zone.name,
                        minutes=s.duration_minutes,
                        source=f"schedule:{s.id}",
                    )
                    s.last_run_minute = current_minute
                    db.commit()
    finally:
        db.close()

@app.on_event("startup")
def start_scheduler():
    try:
        run_migrations()
    except Exception as exc:
        print(f"[db] Migration failed: {exc}")
        return

    if not scheduler.running:
        scheduler.add_job(schedule_tick, "interval", seconds=20)
        scheduler.start()


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)


atexit.register(shutdown_scheduler)
@app.get("/")
def dashboard():
    root = Path(__file__).resolve().parent.parent
    index_path = root / "frontend" / "index.html"
    return FileResponse(
        index_path,
        headers={
            # Ensure clients (and Render's CDN) don't serve a stale dashboard after a deploy
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

