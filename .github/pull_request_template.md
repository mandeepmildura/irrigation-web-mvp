
## Summary
<!-- What does this PR do? Keep it short and clear. -->
- 

## Why
<!-- Why is this change needed? Bug fix, safety, reliability, UX, etc. -->
- 

## Scope
<!-- What areas are affected? (tick all that apply) -->
- [ ] Backend
- [ ] Frontend
- [ ] Scheduler
- [ ] Database / Models
- [ ] Security / Auth
- [ ] Docs only

---

## Safety Checklist (Irrigation App – MUST REVIEW)
- [ ] No overlapping irrigation runs for the same zone
- [ ] Scheduler fails safe (skips on error or missing data)
- [ ] Simulation / dry-run mode does NOT trigger hardware
- [ ] Clear logging for run / skip / failure
- [ ] No secrets or API keys logged

---

## Scheduler & Time
- [ ] Uses `Australia/Melbourne` timezone where required
- [ ] Stores timestamps in UTC
- [ ] Minute / weekday guards prevent duplicate runs
- [ ] DST edge cases considered or safely skipped

---

## Database
- [ ] No new `SessionLocal()` created inside scheduler helpers
- [ ] Same DB session passed through related operations
- [ ] New columns have safe defaults
- [ ] Schema change noted (SQLite DB reset may be required)

---

## API & Security
- [ ] API key enforcement unchanged or improved
- [ ] CORS configuration is valid
- [ ] `/health` endpoint remains accessible
- [ ] OPTIONS / preflight requests are not blocked

---

## Observability
- [ ] Scheduler state is visible (endpoint or logs)
- [ ] Skip reasons are explicit (weekday, moisture, busy, disabled)
- [ ] Errors are logged with messages (not silent)

---

## Testing
<!-- How was this tested? -->
- [ ] `python -m compileall backend`
- [ ] App starts without errors
- [ ] Scheduler starts without exceptions

---

## Notes for Reviewer
<!-- Anything the reviewer should pay special attention to -->
- 
