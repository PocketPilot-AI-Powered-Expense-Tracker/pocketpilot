# PocketPilot — Project Memory

Living record of what the project is, what is built, and what is left.
**Update this file every time the project changes** (add a line to the change log too).

Last updated: 2026-11-26 (GitHub)

## What it is

AI-powered student budget manager. Students set a monthly budget, plan recurring expenses
(rent, tea, travel…), see how much they can safely spend today, review detected UPI payments
before they count, and ask an AI assistant about their money. Currency INR, money stored as
integer paise.

## Stack

| Part | Tech |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS v4, React Router, Axios, Recharts, Lucide |
| Backend | FastAPI, Pydantic v2, PyMongo Async, JWT (PyJWT), bcrypt |
| Database | MongoDB Atlas (database `pocketpilot`) |
| AI | Groq (`openai/gpt-oss-120b`) — Gemini also supported, switch with `AI_PROVIDER` |
| Tests | pytest (176 tests, in-memory fake DB) + `backend/scripts/smoke_test.py` (28 live checks) |
| Deploy (planned) | Backend → Render (`render.yaml`), Frontend → Vercel (`frontend/vercel.json`) |

## How to run locally

Terminal 1 — backend (uses real Atlas + Groq from `backend/.env`):
```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Terminal 2 — frontend:
```bash
cd frontend
VITE_API_URL=http://localhost:8001 npx vite --port 5174 --strictPort
```

Open http://localhost:5174 · API docs at http://localhost:8001/docs

Demo mode (no Atlas, sample data, login `demo@pocketpilot.app` / `demo1234`):
`cd backend && .venv/bin/python scripts/demo_server.py`

Tests: `cd backend && .venv/bin/python -m pytest`

## Secrets

Only in `backend/.env` (gitignored): `MONGODB_URI`, `JWT_SECRET`, `GROQ_API_KEY`.
Never print them, never commit them. Template: `backend/.env.example`.

## Core rules (do not break)

- All money maths is deterministic Python (`backend/app/services/budget_engine.py`). AI never
  calculates official numbers and never touches the database.
- Planned ≠ actual: planned occurrences are not spending until marked spent.
- Pending and rejected UPI payments never affect totals. Accept happens exactly once.
- Every query is filtered by the logged-in user's id.
- Money is integer paise. "Today" uses `APP_TIMEZONE=Asia/Kolkata`.

## What is built

1. **Foundation** — register/login (JWT), budget setup, app layout.
2. **Money tracking** — expenses, income, recurring expenses, planned calendar, budget engine,
   dashboard (safe-to-spend today, remaining, category chart).
3. **UPI review** — detected payments wait in "Review" until accepted; duplicate blocking by
   reference/hash; notification simulator (real detection needs the Android app).
4. **AI** — assistant (picks a calculation, explains it), natural-language actions with
   confirm-first, insights, monthly report. Number guard rejects AI amounts that weren't calculated.
5. **Polish & hardening** — rate limits, production config checks, delete account, deploy files.

Later changes from local testing:
- Routines page merged into the Dashboard as **"Recurring expenses"** (`/routines` redirects
  to `/dashboard#recurring`).
- **Rent** category added.
- Deduction modes: **"Deduct automatically"** (expense created on the due date) or
  **"Deduct when I tap"** (one-tap Spent button in "Coming up").
- Fix: auto-deducted rent now counts in dashboard totals (sync runs before totals).
- When a monthly due day already passed this month, the form asks **"deduct for this month
  too?"** (No by default; Yes records it on the due date).
- **"Already spent this month"** on the Budget page: if the budget month started before today,
  the user enters a rough total spent so far. It is stored as ONE expense (`source: "opening"`,
  category other, dated yesterday, one per budget period, editable/removable by setting 0).
  Preview shows "Left for the rest of the month" and "≈ ₹X / day". Dashboard shows a yellow
  reminder when the month has started but nothing is recorded yet.

## What is remaining

- Git repository: done — https://github.com/muskgpt-oss/pocketpilot (public, branch main).
- Deploy: Render (backend), Vercel (frontend), Atlas Network Access `0.0.0.0/0`, live smoke test.
- Android companion app for real UPI notification detection — design only in
  `android-companion/README.md`, nothing built.
- Optional: chat history, budget history, cookie-based auth, password reset, saved browser tests.

## Key files

- `backend/app/services/budget_engine.py` — budget formulas
- `backend/app/services/routine_service.py` — recurring rules, occurrences, auto-deduction
- `backend/app/services/analytics_service.py` — dashboard numbers
- `backend/app/ai/` — Groq/Gemini providers, prompts, number guard
- `backend/app/utils/upi_parser.py` — UPI notification parser
- `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/RecurringExpenses.jsx`

## Known issues / setup notes

- Atlas only accepts IPs on its Network Access list. If the backend fails on startup with
  `ServerSelectionTimeoutError`, the current internet IP must be added in Atlas
  (Network Access → Add IP Address → Add Current IP Address), then restart the backend.

## Change log

- 2026-11-26 — Initialised git and pushed to https://github.com/muskgpt-oss/pocketpilot (public). backend/.env is gitignored.

- 2026-11-26 — Single-author version of the report: Muskaan Gupta only, guide Prof. Yatish Jain, saved as ~/Downloads/PocketPilot_GenAI_Project_Report_Muskaan_Gupta.pdf and .docx (the two-author version is kept).

- 2026-11-26 — Project report (Generative AI Project format, copied from the SocialLens Project-1 report) saved as ~/Downloads/PocketPilot_GenAI_Project_Report.pdf and .docx (56 pages). Students: Mohammad Rahil Qureshi (EN23CS301623), Muskaan Gupta (EN23CS301639); guide: Prof. Aman Mishra.

- 2026-11-20 — Wiped all accounts and data in the Atlas `pocketpilot` database (fresh start for faculty demo).

- 2026-11-20 — Added "Already spent this month" (Budget page + dashboard reminder), 3 tests.
  Fixed test fake DB applying TTL expiry with the real clock (AI tests failed after 16 Nov).

- 2026-11-20 — Created this memory file.
- Before that: phases 1–5 built; recurring expenses merged into Dashboard; Rent category;
  auto/tap deduction; dashboard totals fix; "deduct for this month too" option.
