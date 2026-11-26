# PocketPilot — AI-Powered Student Budget Manager

PocketPilot helps students **plan** their spending, not just track it. Set a monthly budget,
plan routines like "Tea ₹30 every day", see how much you can safely spend today, review
detected UPI payments before they count, and ask an AI assistant about your money.

| Layer    | Tech |
|----------|------|
| Frontend | React 19, Vite, Tailwind CSS v4, React Router, Axios, Recharts, Lucide |
| Backend  | FastAPI, Pydantic v2, PyMongo Async, JWT (PyJWT), bcrypt |
| Database | MongoDB Atlas |
| AI       | Groq (default, `openai/gpt-oss-120b`) or Gemini, behind a swappable provider interface, backend-only |
| Tests    | Pytest + FastAPI TestClient (in-memory MongoDB fake), end-to-end smoke script |

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Foundation: auth, budget setup, layout | ✅ |
| 2 | Expenses, income, routines, planned calendar, budget engine, dashboard | ✅ |
| 3 | Pending UPI transaction review (simulated notifications) | ✅ |
| 4 | Gemini assistant, natural-language actions, insights, monthly report | ✅ |
| 5 | Polish, hardening, deployment configuration | ✅ |
| — | Android companion app (real notification detection) | 📝 Planned — see `android-companion/README.md` |

Verified against a real MongoDB Atlas cluster and the real Groq API (`scripts/smoke_test.py`).

## Architecture

```
React (Vercel) ──HTTPS + JWT──▶ FastAPI (Render)
                                 ├─ routers/      thin HTTP layer, auth + validation
                                 ├─ services/     business logic
                                 │   ├─ budget_engine.py   pure maths (no DB, no AI)
                                 │   ├─ routine / occurrence / pending / analytics
                                 │   └─ ai_assistant / ai_actions / ai_insights
                                 ├─ ai/provider.py ──▶ Groq or Gemini (text only, no DB access)
                                 └─ db/mongo.py   ──▶ MongoDB Atlas
```

Key rules:
- **All money maths is deterministic Python** (`budget_engine.py`). The AI only chooses a
  calculation and explains its result.
- **Money is integer paise** everywhere (`₹150.50` → `15050`). Fields ending `_paise` are paise.
- **Every query is filtered by the logged-in user's id.** Other users' ids return 404.

## Project structure

```
backend/
  app/
    main.py            app, CORS, error handler, health checks, production checks
    core/              settings, JWT + bcrypt, auth dependency, rate limits
    db/mongo.py        AsyncMongoClient + all indexes
    schemas/           Pydantic request/response models
    services/          business logic (see above)
    routers/           HTTP endpoints
    ai/                provider interface (Gemini), prompts, number guard
    utils/             money, periods, dates, UPI parser, category suggestions
  scripts/
    demo_server.py     run the API with an in-memory DB + sample data
    smoke_test.py      end-to-end checks against any running API
  tests/               141 pytest tests
frontend/
  src/
    pages/             13 screens (lazy-loaded)
    components/        UI kit, charts, modals, simulator, error boundary
    context/           auth + pending-review badge
    services/          axios API wrappers
    hooks/ utils/      data loading, ₹ formatting, dates, constants
android-companion/     design for the notification-listener app (not built)
render.yaml            Render blueprint for the backend
```

## Run locally

### Option A — demo mode (no MongoDB, no keys)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/demo_server.py          # API on http://localhost:8001

cd ../frontend
npm install
VITE_API_URL=http://localhost:8001 npx vite --port 5174
```

Open http://localhost:5174 and log in with `demo@pocketpilot.app` / `demo1234`.
Data lives in memory and resets when the server stops.

### Option B — real database

```bash
cd backend
cp .env.example .env     # fill MONGODB_URI, JWT_SECRET (and optionally GROQ_API_KEY)
.venv/bin/uvicorn app.main:app --reload            # http://localhost:8000, docs at /docs

cd ../frontend
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm run dev
```

- `JWT_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- Atlas: create a free cluster → Database Access (user) → Network Access (your IP) → Connect → Drivers.

### Tests

```bash
cd backend
.venv/bin/python -m pytest                          # 141 unit/API tests, no DB needed
.venv/bin/python scripts/smoke_test.py http://localhost:8000   # 28 end-to-end checks on a real DB
```

The smoke test creates a throwaway account, checks the critical rules (duplicate blocking,
exactly-once actions, pending/rejected payments not counted…) on the real database, then
deletes that account.

## Budget engine

Documented at the top of `backend/app/services/budget_engine.py`:

```
total_income        = allowance + additional income + extra income records
                      (income marked "part of my monthly income" is NOT added again)
remaining_budget    = total_income − actual expenses
reserved_upcoming   = planned occurrences still "planned", dated today … period end
free_to_spend       = remaining_budget − savings_target − reserved_upcoming
daily_budget        = (free money at the start of today) ÷ days remaining
safe_to_spend_today = daily_budget − unplanned spending today
```

Recurring rule → planned occurrence → actual expense are separate collections. Planned
occurrences never count as spending; marking one spent creates exactly one expense (unique
index on `expenses.occurrence_id`); skipping releases its money; rescheduling edits the same
occurrence (unique on `rule_id + original_date`). "Today" uses `APP_TIMEZONE` (Asia/Kolkata).

## Pending UPI transactions

A web app **cannot** read phone notifications, so real detection needs the Android companion
(not built yet). The Review screen has a **notification simulator** that sends sample
PhonePe / Google Pay / Paytm texts through the same parser (`utils/upi_parser.py`).

- Detected payments are `pending_review` and never count until **Add to Expenses**.
- Credits, requests, failures, refunds and cashback are ignored.
- Duplicates are blocked by UPI reference (stored only as a SHA-256 fingerprint + last 4 digits)
  or by notification hash — never by amount + date.
- Accepting is exactly-once: atomic status change, `Idempotency-Key`, unique `expenses.pending_id`.

## AI features (Groq / Gemini)

| Feature | AI does | Backend does |
|---|---|---|
| Assistant | Picks one of 8 calculation tools; words the answer | Runs the tool, returns verified facts |
| Natural-language actions | Fills a structured form | Validates, checks ownership, stores a proposal; executes only after **Confirm**, once |
| Insights | Writes tips | Detects signals (pace, category jumps, small buys…) |
| Monthly report | Writes headline, summary, tips | Calculates every total and comparison |

Safeguards: number guard (AI text with an unverified ₹ amount is replaced by a calculated
answer) · only totals and category names are sent to Gemini · works without a key (labelled
built-in answers) · JSON-schema output re-validated with Pydantic · per-user rate limit ·
12-hour cache · provider is swappable (`app/ai/provider.py`).
Provider: `AI_PROVIDER=groq|gemini|none`. Groq uses `GROQ_MODEL` (default `openai/gpt-oss-120b`, strict JSON-schema
output, see https://console.groq.com/docs/models); Gemini uses `GEMINI_MODEL`. AI text is stripped of markdown before display.

## Security

- Passwords hashed with bcrypt; JWT access tokens (60 min) in `Authorization: Bearer`.
- Login throttled to 10 attempts per email+IP per 10 minutes; AI endpoints rate limited.
- With `ENVIRONMENT=production` the API **refuses to start** if `MONGODB_URI` is localhost,
  `JWT_SECRET` looks like a placeholder, or `FRONTEND_URL` isn't https.
- Unexpected errors return a generic 500 (details only in server logs).
- Users can permanently delete their account and all data (Settings → Delete account).
- Logout is client-side (tokens are stateless and expire). Tokens live in `localStorage`,
  which is simple but readable by injected scripts; a cookie-based session would be stronger.
- Rate limits are in-memory (fine for one Render instance; use Redis if you scale out).

## API

Interactive docs: `http://localhost:8000/docs`. Errors use `{"detail": ...}` with standard
status codes (401, 404, 409, 422, 429, 500).

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` · `/api/health/ready` | Liveness · database readiness |
| POST | `/api/auth/register` · `/api/auth/login` | Create account / log in → token |
| GET · DELETE | `/api/auth/me` | Current user · delete account and all data |
| POST · GET · PUT | `/api/budget` | Create / get / update budget |
| GET · POST | `/api/expenses` | List (`from`, `to`, `category`, `q`, `limit`, `skip`) / create |
| GET · PUT · DELETE | `/api/expenses/{id}` | One expense |
| GET · POST | `/api/income` | List (`from`, `to`, `q`) / create |
| GET · PUT · DELETE | `/api/income/{id}` | One income record |
| GET · POST | `/api/routines` | Recurring routines |
| GET · PUT · DELETE | `/api/routines/{id}` | One routine (delete keeps history) |
| POST | `/api/routines/{id}/pause` · `/resume` | Pause / resume |
| GET | `/api/occurrences` | Planned occurrences (`from`, `to`, `status`) |
| POST | `/api/occurrences/{id}/spend` · `/skip` · `/restore` · `/reschedule` | Occurrence actions |
| POST | `/api/pending-transactions` | Submit detected payment (Android). 201 new / 200 duplicate |
| POST | `/api/pending-transactions/simulate` | Parse a sample notification (testing) |
| GET | `/api/pending-transactions` · `/summary` | List by status + counts · awaiting count |
| POST | `/api/pending-transactions/{id}/accept` · `/reject` · `/restore` | Review actions |
| GET | `/api/analytics/dashboard` · `/safe-to-spend` · `/categories` · `/monthly-comparison` | Analytics |
| GET | `/api/ai/status` | Is AI configured |
| POST | `/api/ai/ask` | Ask a money question |
| POST | `/api/ai/actions/propose` · `/{id}/confirm` · `/{id}/cancel` | Confirm-first actions |
| GET | `/api/ai/insights` · `/api/ai/report?offset=` | Insights · monthly report |

## Deploy

1. **MongoDB Atlas** — free M0 cluster, database user, Network Access `0.0.0.0/0`
   (Render's free tier has no fixed IP; use a strong password). Copy the `mongodb+srv://` URI.
2. **Backend → Render** — push the repo to GitHub, Render → New → Blueprint → select the repo
   (`render.yaml`). Set `MONGODB_URI`, `FRONTEND_URL` (your Vercel URL) and optionally
   `GROQ_API_KEY`. `JWT_SECRET` is generated automatically.
   Check `https://<api>.onrender.com/api/health/ready` → `{"database":"ok"}`.
3. **Frontend → Vercel** — import the repo, root directory `frontend`, framework Vite,
   env `VITE_API_URL=https://<api>.onrender.com`. `vercel.json` handles client-side routes.
4. Update `FRONTEND_URL` on Render to the final Vercel URL, then run
   `scripts/smoke_test.py https://<api>.onrender.com`.

Free Render services sleep when idle; the first request after a while can take ~30–60 s.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot reach the server" in the app | Backend not running, or `VITE_API_URL` wrong |
| CORS error in browser console | Add the exact frontend origin to `FRONTEND_URL` |
| API exits on startup: "Unsafe production settings" | Fix the listed settings, or unset `ENVIRONMENT` locally |
| API hangs then fails on startup | Atlas Network Access doesn't allow your IP / wrong URI |
| Assistant says "AI is not configured" | Set `AI_PROVIDER=groq` and `GROQ_API_KEY`, restart the backend |
| AI answers fall back to built-in text | Check the server log for `AI ... failed`; verify the key and `GROQ_MODEL` |
