from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo
import atexit

from db import Base, engine, get_db, SessionLocal
import models, schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Irrigation Web MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TEMP for testing; lock down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def create_zone(payload: schemas.ZoneCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Zone).filter(models.Zone.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Zone name already exists")
    z = models.Zone(name=payload.name, description=payload.description)
    db.add(z)
    db.commit()
    db.refresh(z)
    return z

@app.get("/zones", response_model=list[schemas.ZoneOut])
def list_zones(db: Session = Depends(get_db)):
    return db.query(models.Zone).order_by(models.Zone.id).all()

# ---------- Schedules ----------
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
        last_run_minute=None,  # new
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/schedules", response_model=list[schemas.ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).order_by(models.Schedule.id).all()

# ---------- Manual run (logs to DB) ----------
@app.post("/run/{zone_name}", response_model=schemas.RunOut)
def run_zone(zone_name: str, minutes: int = 10, source: str = "manual"):
    return execute_run(zone_name=zone_name, minutes=minutes, source=source)

# ---------- Run history ----------
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

# ---------- Sensors ----------
@app.post("/readings", response_model=schemas.SensorReadingOut)
def add_reading(payload: schemas.SensorReadingCreate, db: Session = Depends(get_db)):
    r = models.SensorReading(zone_name=payload.zone_name, metric=payload.metric, value=payload.value)
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

# ---------- Scheduler (skip missed; never double-run within same minute) ----------
scheduler = BackgroundScheduler(timezone="Australia/Melbourne")

def schedule_tick():
    mel_now = datetime.now(ZoneInfo("Australia/Melbourne"))
    current_minute = mel_now.strftime("%H:%M")

    db = SessionLocal()
    try:
        schedules = db.query(models.Schedule).filter(models.Schedule.enabled == 1).all()

        for s in schedules:
            # run once per matching minute
            if s.start_time == current_minute and s.last_run_minute != current_minute:
                zone = db.query(models.Zone).filter(models.Zone.id == s.zone_id).first()
                if zone:
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
    if not scheduler.running:
        scheduler.add_job(schedule_tick, "interval", seconds=20)
        scheduler.start()

atexit.register(lambda: scheduler.shutdown(wait=False))
@app.get("/")
def dashboard():
    return FileResponse("../frontend/index.html")

