from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db import Base, engine, get_db
import models, schemas

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Irrigation Web MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TEMP for testing (lock down later)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

# Zones
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

# Schedules
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
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/schedules", response_model=list[schemas.ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).order_by(models.Schedule.id).all()

# Manual run (later: call Home Assistant / MQTT here)
@app.post("/run/{zone_name}")
def run_zone(zone_name: str, minutes: int = 10):
    return {"action": "RUN", "zone": zone_name, "duration_minutes": minutes}

# Sensors
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
