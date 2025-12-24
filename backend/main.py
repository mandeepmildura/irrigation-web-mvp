from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os

from apscheduler.schedulers.background import BackgroundScheduler

from db import Base, engine, get_db
import models

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------

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
API_KEY = os.getenv("API_KEY", "").strip()

# -------------------------------------------------
# SERVE FRONTEND
# -------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))   # /backend
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# -------------------------------------------------
# AUTH (simple)
# -------------------------------------------------

def require_key(request: Request):
    if not API_KEY:
        return  # if you forgot to set it, don't block (but set it on Render!)
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# -------------------------------------------------
# HEALTH
# -------------------------------------------------

@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {"ok": True, "db_ready": True, "ts": datetime.now(LOCAL_TZ).isoformat()}

# -------------------------------------------------
# HELPERS
# -------------------------------------------------

def parse_days(days: str) -> set[str]:
    d = (days or "*").strip().lower()
    if d == "*" or d == "":
        return {"mon","tue","wed","thu","fri","sat","sun"}
    return {x.strip()[:3] for x in d.split(",") if x.strip()}

def now_local():
    return datetime.now(LOCAL_TZ)

def zone_default_minutes(zone: "models.Zone") -> int:
    """
    Farm logic v1 without DB changes:
    Put default minutes inside Zone.description like:
      "Avocado orchard - south | default=10"
    """
    desc = (zone.description or "")
    desc_lower = desc.lower()
    if "default=" in desc_lower:
        try:
            part = desc_lower.split("default=", 1)[1]
            num = ""
            for ch in part:
                if ch.isdigit():
                    num += ch
                else:
                    break
            if num:
                return max(1, int(num))
        except:
            pass
    return 10  # fallback default

def should_trigger_schedule(s: "models.Schedule", dt_local: datetime) -> bool:
    if not s.enabled:
        return False
    # match time to minute
    hhmm = dt_local.strftime("%H:%M")
    if (s.start or "").strip() != hhmm:
        return False
    # match day
    day = dt_local.strftime("%a").lower()[:3]  # mon,tue...
    allowed = parse_days(s.days or "*")
    return day in allowed

def already_ran_recently(db: Session, schedule_id: int) -> bool:
    """
    Prevent duplicates without DB schema change:
    if we have a run from this schedule within the last 90 seconds, skip.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=90)
    src = f"schedule:{schedule_id}"
    existing = (
        db.query(models.Run)
        .filter(models.Run.source == src)
        .filter(models.Run.ts >= cutoff)
        .first()
    )
    return existing is not None

def actuator_start(zone: "models.Zone", minutes: int):
    """
    TODO later: actually call relay/HA/PLC here.
    For now: logging is the "truth" (like your MVP).
    """
    return

# -------------------------------------------------
# SCHEDULER (AUTORUN)
# -------------------------------------------------

scheduler = BackgroundScheduler()

def tick():
    db = None
    try:
        db = next(get_db())
        dt = now_local().replace(second=0, microsecond=0)

        schedules = db.query(models.Schedule).all()
        for s in schedules:
            if not should_trigger_schedule(s, dt):
                continue
            if already_ran_recently(db, s.id):
                continue

            zone = db.query(models.Zone).filter(models.Zone.id == s.zone_id).first()
            if not zone:
                continue

            mins = int(s.minutes or 0)
            if mins <= 0:
                mins = zone_default_minutes(zone)

            actuator_start(zone, mins)

            r = models.Run(
                zone_id=zone.id,
                duration_minutes=mins,
                source=f"schedule:{s.id}",
                ts=datetime.utcnow(),
            )
            db.add(r)
            db.commit()

    except Exception:
        # keep scheduler alive even if one tick fails
        if db:
            db.rollback()
    finally:
        try:
            if db:
                db.close()
        except:
            pass

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(tick, "interval", seconds=30, id="schedule_tick", replace_existing=True)
    scheduler.start()

@app.on_event("shutdown")
def stop_scheduler():
    try:
        scheduler.shutdown()
    except:
        pass

# -------------------------------------------------
# ADMIN
# -------------------------------------------------

@app.delete("/admin/schedules")
def reset_schedules(request: Request, db: Session = Depends(get_db)):
    require_key(request)
    deleted = db.query(models.Schedule).delete()
    db.commit()
    return {"ok": True, "deleted": deleted}

# -------------------------------------------------
# ZONES
# -------------------------------------------------

@app.post("/zones")
def create_zone(request: Request, name: str, description: str = "", db: Session = Depends(get_db)):
    require_key(request)
    zone = models.Zone(name=name, description=description)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone

@app.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    return db.query(models.Zone).all()
def cols(model):
    return {c.name for c in model.__table__.columns}

def build_kwargs(model, data: dict):
    c = cols(model)
    return {k: v for k, v in data.items() if k in c}

# -------------------------------------------------
# SCHEDULES
# -------------------------------------------------

@app.post("/schedules")
def create_schedule(
    request: Request,
    zone_id: int,
    start: str,
    minutes: int,
    days: str = "*",
    enabled: bool = True,
    db: Session = Depends(get_db),
):
    require_key(request)

    c = cols(models.Schedule)
    data = {"zone_id": zone_id, "days": days, "enabled": enabled}

    # start field name may differ
    if "start" in c:
        data["start"] = start
    elif "start_time" in c:
        data["start_time"] = start

    # minutes field name may differ
    if "minutes" in c:
        data["minutes"] = minutes
    elif "duration_minutes" in c:
        data["duration_minutes"] = minutes
    elif "duration" in c:
        data["duration"] = minutes

    sched = models.Schedule(**build_kwargs(models.Schedule, data))
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched

@app.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    return db.query(models.Schedule).all()

# -------------------------------------------------
# MANUAL RUN
# -------------------------------------------------

@app.post("/run")
def manual_run(request: Request, zone_id: int, minutes: int, db: Session = Depends(get_db)):
    require_key(request)

    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    mins = int(minutes or 0)
    if mins <= 0:
        mins = zone_default_minutes(zone)

    actuator_start(zone, mins)

    c = cols(models.Run)
    data = {"zone_id": zone_id, "source": "manual"}

    # duration field name may differ
    if "duration_minutes" in c:
        data["duration_minutes"] = mins
    elif "minutes" in c:
        data["minutes"] = mins
    elif "duration" in c:
        data["duration"] = mins

    # timestamp field name may differ
    if "ts" in c:
        data["ts"] = datetime.utcnow()
    elif "created_at" in c:
        data["created_at"] = datetime.utcnow()
    elif "time" in c:
        data["time"] = datetime.utcnow()

    run = models.Run(**build_kwargs(models.Run, data))
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# -------------------------------------------------
# RUN HISTORY
# -------------------------------------------------

@app.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    c = cols(models.Run)
    if "ts" in c:
        order_col = models.Run.ts
    elif "created_at" in c:
        order_col = models.Run.created_at
    else:
        order_col = None

    q = db.query(models.Run)
    if order_col is not None:
        q = q.order_by(order_col.desc())

    return q.limit(100).all()
