Below is a **drop-in `TECHNICAL_SPEC.md`** tailored to **GymGenius** and written in the same voice / structure as your “Schwerhörige-Hexe Benchmark” spec.

```markdown
# **TECHNICAL SPECIFICATION – “GymGenius Adaptive Coach”**

*Version 1.0 – 14 Jun 2025*

**Note:** This document appears to describe a system architecture (React, Node API, Prisma, gRPC) that differs significantly from the currently implemented VanillaJS frontend and Flask/Python backend. The following sections have been partially updated to reflect the *existing* codebase's structure and dependencies as of October 2023, but a full rewrite would be needed for complete accuracy with the current implementation. The primary focus of the recent review was on the existing codebase.

---

## 1 · Project Overview

GymGenius is a **monorepo** that ships a mobile-first PWA (VanillaJS) and a Python/Flask backend (API and worker).
Goal: deliver real-time weight/rep/rest prescriptions that adapt to each user’s history, recovery, and goals.

**Pipeline (stateless per service):**

1. **Web PWA** – logs set, fetches recommendation via REST (Vanilla JS, HTML, CSS).
2. **API (Engine)** – Flask/Python backend; auth, validation, business logic, serves recommendations, queues jobs via RQ.
3. **Worker (Engine)** – Python RQ worker; processes background tasks (e.g., analytics, future ML model updates).
4. **Storage** – Postgres (relational data), Redis (RQ queue and potentially caching).

All compute nodes are **stateless**; persistence lives only in Postgres and Redis.

---

## 2 · Repository / File Structure

```markdown
gymgenius/
├── README.md
├── HOW_TO_USE.md
├── ROADMAP.md
├── ARCHITECTURE.md
├── TECHNICAL_SPEC.md
├── AGENT_GUIDE.md
├── CONTRIBUTING.md
├── LICENSE.md
├── Makefile
├── docker-compose.yml
├── .env.example
├── database/
│   ├── create_schema.py
│   └── seed_data.py
├── engine/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── blueprints/
│   └── worker.py
├── webapp/
│   ├── index.html
│   ├── js/app.js
│   ├── css/style.css
│   ├── Dockerfile
│   └── default.conf (Nginx config)
├── tests/
│   └── # Python tests for engine
└── webapp/tests/ # JS tests or Python tests for web aspects
```

### 2.1 Key Files

| File / Dir                 | Purpose                                                         | Notable Imports / Tools                |
|----------------------------|-----------------------------------------------------------------|----------------------------------------|
| **database/create_schema.py** | Python script to define and create PostgreSQL schema.          | psycopg2                               |
| **database/seed_data.py**  | Python script to populate database with initial data.           | psycopg2                               |
| **engine/app.py**          | Main Flask application file for the backend API.                | Flask, PyJWT, psycopg2                 |
| **engine/worker.py**       | Python RQ worker for background tasks.                          | rq, redis                              |
| **webapp/js/app.js**       | Main JavaScript file for frontend logic and interactivity.      | Vanilla JS, Fetch API                  |
| **webapp/default.conf**    | Nginx configuration for serving frontend and proxying API.      | Nginx                                  |
| **docker-compose.yml**     | Defines and configures multi-container local dev environment.   | Docker Compose                         |
| **Makefile**               | Provides helper commands for building, running, testing.        | Make                                   |

---

## 3 · Data-Flow Specification

### 3.1 Core Data Models
The database schema is defined imperatively in `database/create_schema.py` using SQL commands. Key tables include `users`, `exercises`, `workouts`, and `workout_sets`. Refer to this script for detailed table structures and relationships.

### 3.2 `POST /recommendation` (API → Engine)

| Field           | Type      | Description                        |
| --------------- | --------- | ---------------------------------- |
| `user_id`       | UUID      |                                    |
| `exercise_id`   | UUID      |                                    |
| `set_number`    | int       | 1-based index within session       |
| `goal_strength` | float     | 0-1 slider                         |
| `history`       | object\[] | last 12 sets `{w,r,rir,timestamp}` |

`api` maps the JSON body to `PredictSetRequest` (proto) and forwards synchronously to `engine`.

### 3.3 `engine` Response

```jsonc
{
  "weight": 80.0,          // kg, pre-rounded
  "rep_low": 6,
  "rep_high": 8,
  "rir": 2,
  "confidence": 0.83,
  "explanation": "load derived from 1RM 105.2kg, fatigue −5%"
}
```

`api` persists the recommendation, applies plate rounding, returns to web.

---

## 4 · Algorithmic Core (Engine)

* **Load estimation** – Extended Epley with user-specific RIR-bias:
  $\hat{1RM} = \frac{w}{1 - 0.0333\,(r + \max(0,\,RIR - b_u))}$

* **Goal interpolation** (see `calculate_training_params` in spec).

* **Fatigue decay** – impulse-response:
  $F_t = \sum V\!L_j^\alpha e^{-\beta\Delta t}$; personalised $\alpha,\beta$ via HMC.

* **Readiness modifier** – z-score of HRV, sleep, fatigue questionnaire → ±7 %.

* **Guardrails** – clamp inter-session load delta ≤ 7.5 %.

`model.py` exports two public methods:

```python
def predict(request: PredictSetRequest) -> PredictSetResponse: ...
def warm_start(user_id: str) -> None  # batch import of history
```

---

## 5 · REST API Surface (OpenAPI snippets)

| Verb   | Path                   | Purpose                             | Auth   |
| ------ | ---------------------- | ----------------------------------- | ------ |
| `POST` | `/v1/login`            | JWT issuance                        | none   |
| `POST` | `/v1/sets`             | Log actual performance              | Bearer |
| `POST` | `/v1/recommendation`   | Get next-set prescription           | Bearer |
| `GET`  | `/v1/analytics/volume` | Muscle-volume weekly graph          | Bearer |
| `POST` | `/v1/plan/compile`     | Generate workout template from goal | Bearer |

All endpoints validated with **zod** → automatic OpenAPI JSON.

---

## 6 · Dev Environment & Commands

```bash
# spin up full stack (web, engine, db, redis)
make dev

# run linters (ruff for Python, node --check for JS)
make lint

# run tests (pytest for engine and webapp tests)
make test

# initialize/update database schema
docker compose exec engine python database/create_schema.py

# seed initial data
docker compose exec engine python database/seed_data.py

# run background worker
docker compose exec engine python -m engine.worker
```

---

## 7 · Logging & Monitoring

| Layer  | Library           | Format → Sink                                 | Notes             |
| ------ | ----------------- | --------------------------------------------- | ----------------- |
| Node   | pino              | JSON → stdout                                 | trace-ID attached |
| Python | structlog         | JSON → stdout                                 |                   |
| Traces | opentelemetry SDK | OTLP → Datadog APM                            | 90-day retention  |
| Alerts | Datadog           | **P95** `/predict` > 300 ms, error rate > 2 % |                   |

---

## 8 · Implementation Phases & Milestones (superset of ROADMAP)

| Phase | Modules                           | Goal                       | Tests                    |
| ----- | --------------------------------- | -------------------------- | ------------------------ |
| **0** | `database`, auth scaffold         | Schema locked, login works | prisma client unit tests |
| **1** | `engine` v0 (pure Extended Epley) | Prediction ≤ ±10 % MAE     | pytest fixture history   |
| **2** | `web` logging loop                | 3-tap set logging UX       | cypress e2e smoke        |
| **3** | fatigue & readiness layer         | MAE ≤ 5 %; guardrails pass | scenario tests           |
| **4** | plan templates & analytics        | day-7 retention ≥ 50 users | jest snapshots           |
| **5** | staging env, observability        | <150 ms P95 latency        | k6 load test             |
| **6** | subscription Stripe flow          | revenue > \$0              | stripe mock tests        |

*MVP = Phases 0–3.*

---

## 9 · Edge Cases & Guardrails

| Case                               | Handling                                         |
| ---------------------------------- | ------------------------------------------------ |
| **Weight jump request > 7.5 %**    | Engine clamps, returns `flag: "hard_cap"`        |
| **User logs `RIR = –1`**           | Reject 422, front-end tooltip                    |
| **Set not logged within 30 min**   | Session auto-expires; next workout bump rest day |
| **Engine latency > 1 s**           | API falls back to last-session heuristic         |
| **Cold start (no history at all)** | Onboard 5-rep AMRAP test; population priors      |
| **JWT expired**                    | 401 → web triggers silent refresh & retry        |

---

## 10 · Best-Practices Checklist

* **Typing** – `tsconfig strict` · `mypy --strict`.
* **Secrets** – .env only; populated via AWS Secrets Manager in prod.
* **CI** – lint → test → docker build → trivy scan; fail fast.
* **Async** – Node routes non-blocking; Python uses `asyncio`, no GIL-heavy ops.
* **Docs** – every public fn/docstring + OpenAPI auto-generated.
* **Coverage** ≥ 80 % lines for **both** stacks.
* **Containers** – rootless; health-check `/healthz`.
* **Guardrails** – weight delta ≤ 7.5 %, volume delta ≤ 30 %.
* **Observability** – trace ID propagated (`x-request-id`) across services.

---

## 11 · Dependencies (≥ Version)

| Package                    | Purpose                                  |
| -------------------------- | ---------------------------------------- |
| **Python** 3.11            | Backend engine and worker runtime        |
| **Flask** 2.x              | Backend API framework                    |
| **psycopg2-binary**        | PostgreSQL adapter for Python            |
| **PyJWT**                  | JWT authentication                       |
| **bcrypt**                 | Password hashing                         |
| **rq**                     | Redis Queue for background tasks         |
| **redis** (Python package) | Redis client for Python                  |
| **Vanilla JavaScript (ES6+)** | Frontend logic                           |
| **Nginx**                  | Web server and reverse proxy             |
| **Docker / Docker Compose**| Containerization and local orchestration |
| **PostgreSQL** 16          | Database                                 |
| **Redis** (Server)         | In-memory store for task queue/cache     |
| **pytest**                 | Python testing framework                 |
| **ruff**                   | Python linter                            |

---

## 12 · Next Steps

1. **Clone repo**, create `.env`, run `make dev`.
2. Implement **Phase 0** migrations → `pnpm db:generate`.
3. Smoke‐test `POST /recommendation` with sample history (script in `scripts/demo.py`).
4. Keep `ROADMAP.md` in sync—bots rely on task IDs.

*Specification complete – further questions should be answerable by this document or existing meta-files.* 💪

```


