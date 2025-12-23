from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo

from db import Base, engine, get_db
import models

# -------------------------------------------------------------------
# APP SETUP
# -------------------------------------------------------------------

app = FastAPI(title="Irrigation Web MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

LOCAL_TZ = ZoneInfo("Australia/Melbourne")

# -------------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "ok": True,
        "db_ready": True,
        "ts": datetime.now(LOCAL_TZ).isoformat()
    }

# -------------------------------------------------------------------
# ADMIN – RESET SCHEDULES (THIS IS THE ONLY NEW LOGIC)
# -------------------------------------------------------------------

@app.delete("/admin/schedules")
def reset_schedules(db: Session = Depends(get_db)):
    deleted = db.query(models.Schedule).delete()
    db.commit()
    return {"ok": True, "deleted": deleted}

# -------------------------------------------------------------------
# ZONES
# -------------------------------------------------------------------

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

# -------------------------------------------------------------------
# SCHEDULES (SIMPLE + CLEAN)
# -------------------------------------------------------------------

@app.post("/schedules")
def create_schedule(
    zone_id: int,
    start: str,          # "06:30"
    minutes: int,
    days: str = "*",
    enabled: bool = True,
    db: Session = Depends(get_db),
):
    s = models.Schedule(
        zone_id=zone_id,
        start=start,
        minutes=minutes,
        days=days,
        enabled=enabled,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).all()

# -------------------------------------------------------------------
# MANUAL RUN
# -------------------------------------------------------------------

@app.post("/run")
def manual_run(zone_id: int, minutes: int, db: Session = Depends(get_db)):
    r = models.Run(
        zone_id=zone_id,
        duration_minutes=minutes,
        source="manual",
        ts=datetime.utcnow()
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

# -------------------------------------------------------------------
# RUN HISTORY
# -------------------------------------------------------------------

@app.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    return (
        db.query(models.Run)
        .order_by(models.Run.ts.desc())
        .limit(100)
        .all()
    )
