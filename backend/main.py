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

Base.metadata.create_all(bind=engine)

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
# HELPERS (prevents 500s if models differ)
# -------------------------------------------------

def cols(model):
    return {c.name for c in model.__table__.columns}

def safe_create(model, data: dict):
    c = cols(model)
    clean = {k: v for k, v in data.items() if k in c}
    return model(**clean)

# -------------------------------------------------
# HEALTH
# -------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True, "db_ready": True, "ts": datetime.utcnow().isoformat()}

# -------------------------------------------------
# DEBUG (IMPORTANT)
# -------------------------------------------------

@app.get("/debug/schema")
def debug_schema():
    return {
        "Zone": list(cols(models.Zone)),
        "Schedule": list(cols(models.Schedule)),
        "Run": list(cols(models.Run)),
    }

# -------------------------------------------------
# ZONES
# -------------------------------------------------

@app.post("/zones")
def create_zone(name: str, description: str = "", db: Session = Depends(get_db)):
    z = safe_create(models.Zone, {
        "name": name,
        "description": description
    })
    db.add(z)
    db.commit()
    db.refresh(z)
    return z

@app.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    return db.query(models.Zone).all()

# -------------------------------------------------
# SCHEDULES
# -------------------------------------------------

@app.post("/schedules")
def create_schedule(
    zone_id: int,
    start: str,
    minutes: int,
    days: str = "*",
    enabled: bool = True,
    db: Session = Depends(get_db),
):
    s = safe_create(models.Schedule, {
        "zone_id": zone_id,
        "start": start,
        "start_time": start,
        "minutes": minutes,
        "duration_minutes": minutes,
        "days": days,
        "enabled": enabled,
    })
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@app.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).all()

# -------------------------------------------------
# MANUAL RUN
# -------------------------------------------------

@app.post("/run")
def manual_run(zone_id: int, minutes: int, db: Session = Depends(get_db)):
    r = safe_create(models.Run, {
        "zone_id": zone_id,
        "minutes": minutes,
        "duration_minutes": minutes,
        "source": "manual",
        "ts": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    })
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

@app.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    q = db.query(models.Run)
    c = cols(models.Run)
    if "ts" in c:
        q = q.order_by(models.Run.ts.desc())
    elif "created_at" in c:
        q = q.order_by(models.Run.created_at.desc())
    return q.limit(100).all()