"""Run PocketPilot's API with an IN-MEMORY database and sample data (no MongoDB needed).

    cd backend
    .venv/bin/python scripts/demo_server.py            # http://localhost:8001
    .venv/bin/python scripts/demo_server.py --port 8000 --frontend http://localhost:5173

Demo login: demo@pocketpilot.app / demo1234
Everything is lost when the server stops. Needs requirements-dev.txt (mongomock).
For real use, set MONGODB_URI in backend/.env and run uvicorn normally.
"""
import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8001)
parser.add_argument("--frontend", default="http://localhost:5174")
parser.add_argument("--no-seed", action="store_true")
args = parser.parse_args()

os.environ["FRONTEND_URL"] = f"{args.frontend},http://localhost:5173,http://localhost:5174"
os.environ.setdefault("JWT_SECRET", "demo-only-secret-key-not-for-production-use-1234")

import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.mongo import ensure_indexes, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.utils import dates  # noqa: E402
from tests.fake_db import FakeDatabase  # noqa: E402

db = FakeDatabase()
asyncio.run(ensure_indexes(db))
app.dependency_overrides[get_db] = lambda: db


@asynccontextmanager
async def _no_mongo_lifespan(_):
    yield

app.router.lifespan_context = _no_mongo_lifespan


def seed() -> None:
    c = TestClient(app)
    token = c.post("/api/auth/register", json={"name": "Asha Rao", "email": "demo@pocketpilot.app",
                                               "password": "demo1234"}).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    today = dates.app_today()
    start = today.replace(day=1)
    c.post("/api/budget", json={"monthly_allowance_paise": 800000, "additional_income_paise": 50000,
                                "savings_target_paise": 150000, "period_start_day": 1})

    def d(days_ago: int) -> str:
        return max(start, today - timedelta(days=days_ago)).isoformat()

    prev = (start - timedelta(days=1)).replace(day=10).isoformat()
    for amt, cat, desc, day in [
        (15000, "food", "Canteen lunch", d(3)), (4000, "transportation", "Auto to college", d(3)),
        (49900, "shopping", "Notebook & pens", d(2)), (19900, "subscriptions", "Spotify", d(2)),
        (22000, "food", "Dinner with friends", d(1)), (6000, "transportation", "Metro card top-up", d(1)),
        (12000, "food", "Momos", d(0)), (180000, "food", "Food (last month)", prev),
        (90000, "shopping", "Clothes (last month)", prev),
    ]:
        c.post("/api/expenses", json={"amount_paise": amt, "category": cat, "description": desc, "date": day})
    c.post("/api/income", json={"amount_paise": 800000, "source": "Pocket money", "date": start.isoformat(),
                                "counts_as_planned": True})
    c.post("/api/income", json={"amount_paise": 100000, "source": "Gift", "date": d(1), "description": "From grandma"})
    c.post("/api/routines", json={"name": "Tea", "amount_paise": 3000, "category": "food", "frequency": "daily"})
    c.post("/api/routines", json={"name": "Outside food", "amount_paise": 20000, "category": "food",
                                  "frequency": "weekly", "weekday": 6})
    c.post("/api/routines", json={"name": "Movie", "amount_paise": 30000, "category": "entertainment",
                                  "frequency": "monthly", "day_of_month": 20})
    now = dates.utc_now()
    for app_name, title, text, mins in [
        ("phonepe", "Payment Successful", "₹120 paid to Campus Cafe. UPI Ref No. 432112345678", 90),
        ("gpay", "Google Pay", "You paid ₹500.00 to Rahul Sharma using UPI. UPI transaction ID 532198765432", 60),
        ("paytm", "Paytm", "Rs.249 paid to Swiggy successfully. Ref: 612345098765", 30),
    ]:
        c.post("/api/pending-transactions/simulate",
               json={"source_app": app_name, "title": title, "text": text,
                     "posted_at": (now - timedelta(minutes=mins)).isoformat()})
    print(token, flush=True)


if not args.no_seed:
    seed()
print(f"PocketPilot demo API on http://localhost:{args.port}  (login demo@pocketpilot.app / demo1234)", flush=True)
uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
