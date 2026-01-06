from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import os
import traceback

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

# Create tables if possible (won’t crash app)
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

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
    return {
        "ok": True,
        "ts": datetime.utcnow().isoformat()
    }

# -------------------------------------------------
# DEBUG (WILL NEVER 500)
# -------------------------------------------------

@app.get("/debug/schema")
def debug_schema():
    out = {}
    errors = {}

    for name, model in {
        "Zone": getattr(models, "Zone", None),
        "Schedule": getattr(models, "Schedule", None),
        "Run": getattr(models, "Run", None),
    }.items():
        try:
            if model is None:
                out[name] = "MODEL NOT FOUND"
            else:
                out[name] = [c.name for c in model.__table__.columns]
        except Exception as e:
            errors[name] = str(e)

    return JSONResponse({
        "schema": out,
        "errors": errors,
    })

# -------------------------------------------------
# ZONES (MINIMAL, SAFE)
# -------------------------------------------------

@app.post("/zones")
def create_zone(name: str, description: str = "", db: Session = Depends(get_db)):
    try:
        z = models.Zone(name=name, description=description)
        db.add(z)
        db.commit()
        db.refresh(z)
        return z
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()}
        )

@app.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    return db.query(models.Zone).all()

# -------------------------------------------------
# SCHEDULES (MINIMAL)
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
    try:
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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()}
        )

@app.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).all()

# -------------------------------------------------
# RUNS
# -------------------------------------------------

@app.post("/run")
def manual_run(zone_id: int, minutes: int, db: Session = Depends(get_db)):
    try:
        r = models.Run(
            zone_id=zone_id,
            minutes=minutes,
            source="manual",
            created_at=datetime.utcnow(),
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return r
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()}
        )

@app.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    return db.query(models.Run).limit(100).all()