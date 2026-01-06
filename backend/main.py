from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import os

from db import Base, engine, get_db
import models

# -------------------------------------------------
# APP
# -------------------------------------------------

app = FastAPI(title="Irrigation Web MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Do NOT auto-create tables on Render
# Base.metadata.create_all(bind=engine)

# -------------------------------------------------
# FRONTEND
# -------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# -------------------------------------------------
# HEALTH
# -------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True, "ts": datetime.utcnow().isoformat()}

# -------------------------------------------------
# ZONES
# -------------------------------------------------

@app.post("/zones")
def create_zone(name: str, description: str = "", db: Session = Depends(get_db)):
    z = models.Zone(name=name, description=description)
    db.add(z)
    db.commit()
    db.refresh(z)
    return z

@app.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    return db.query(models.Zone).all()

# -------------------------------------------------
# SCHEDULES (MATCHES REAL COLUMNS)
# -------------------------------------------------

@app.post("/schedules")
def create_schedule(
    zone_id: int,
    start_time: str,
    duration_minutes: int,
    days_of_week: str = "*",
    enabled: bool = True,
    skip_if_moisture_over: int | None = None,
    moisture_lookback_minutes: int | None = None,
    db: Session = Depends(get_db),
):
    s = models.Schedule(
        zone_id=zone_id,
        start_time=start_time,
        duration_minutes=duration_minutes,
        days_of_week=days_of_week,
        enabled=enabled,
        skip_if_moisture_over=skip_if_moisture_over,
        moisture_lookback_minutes=moisture_lookback_minutes,
        last_run_minute=None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).all()

# -------------------------------------------------
# RUNS (DISABLED — MODEL DOES NOT EXIST)
# -------------------------------------------------

@app.post("/run")
def manual_run():
    raise HTTPException(
        status_code=501,
        detail="Run table not implemented yet"
    )

@app.get("/runs")
def list_runs():
    return []