Below is a **drop-in `TECHNICAL_SPEC.md`** tailored to **GymGenius** and written in the same voice / structure as your “Schwerhörige-Hexe Benchmark” spec.

```markdown
# **TECHNICAL SPECIFICATION – “GymGenius Adaptive Coach”**

*Version 1.0 – 14 Jun 2025*

---

## 1 · Project Overview

GymGenius is a **monorepo** that ships a mobile-first PWA, a Node API, and a Python ML micro-service.  
Goal: deliver real-time weight/rep/rest prescriptions that adapt to each user’s history, recovery, and goals.

**Pipeline (stateless per service):**

1. **Web PWA** – logs set, fetches recommendation via REST.
2. **API** – auth, validation, orchestration, queues jobs.
3. **Engine** – gRPC micro-service; predicts weight, learns RIR-bias & recovery τ.
4. **Worker** – nightly fine-tunes models, aggregates analytics.
5. **Storage** – Postgres (relational), Redis (cache/queue), S3 (model ckpts, exports).
6. **Observability** – OpenTelemetry traces, Sentry errors, Datadog metrics.

All compute nodes are **stateless**; persistence lives only in Postgres, Redis, and S3.

---

## 2 · Repository / File Structure

```

gymgenius/
├── README.md              # pitch + quick-start
├── ROADMAP.md             # phase backlog
├── ARCHITECTURE.md        # service registry + diagrams
├── AGENT\_GUIDE.md         # bot rules
├── CONTRIBUTING.md
├── LICENSE.md
├── docker-compose.yml
├── .env.example
├── apps/
│   ├── web/               # React + TS PWA
│   └── api/               # Express/Fastify service
├── services/
│   ├── engine/            # PyTorch adaptive engine
│   └── worker/            # Bull queue consumer
├── packages/
│   └── ui/                # Tailwind component library
├── database/
│   ├── schema.prisma
│   ├── migrations/
│   └── seed.ts
├── infra/                 # Terraform / ECS / GitHub Actions manifests
├── scripts/               # one-off helpers
└── tests/
├── web/
├── api/
└── engine/

````

### 2.1 Key Files

| File / Dir                 | Purpose                                                         | Notable Imports / Tools                |
|----------------------------|-----------------------------------------------------------------|----------------------------------------|
| **schema.prisma**          | Postgres schema incl. enums, relations                          | Prisma ORM                             |
| **engine/model.py**        | PyTorch-Lightning module (extended Epley, Bayesian layers)      | torch, pyro-ppl                        |
| **engine/api.proto**       | gRPC contract (`PredictSet`, `WarmStart`)                       | protobuf 3                             |
| **api/routes/sets.ts**     | `POST /sets` & `GET /recommendation`                            | zod validation, OpenAPI decorators     |
| **worker/train.py**        | Nightly fine-tune script, pushes ckpt to S3                     | boto3, pandas                          |
| **web/src/hooks/usePredict.ts** | React SWR hook → `/recommendation`                          | zustand, ky, msw                       |
| **infra/ci.yml**           | GitHub Actions: lint-test-docker-deploy                         | pnpm, pytest, ruff, kubectl            |

---

## 3 · Data-Flow Specification

### 3.1 Core Prisma Models

```prisma
model User {
  id              String   @id @default(uuid())
  email           String   @unique
  passwordHash    String
  goalSlider      Float    @default(0.5)   // 0 = hypertrophy, 1 = strength
  rirBias         Float    @default(2.0)
  createdAt       DateTime @default(now())
  workouts        Workout[]
}

model Workout {
  id          String   @id @default(uuid())
  user        User     @relation(fields: [userId], references: [id])
  userId      String
  startedAt   DateTime
  completedAt DateTime?
  sessionRpe  Int?
  sets        WorkoutSet[]
}

model WorkoutSet {
  id                 String  @id @default(uuid())
  workout            Workout @relation(fields: [workoutId], references: [id])
  workoutId          String
  exerciseId         String
  setNumber          Int
  recommendedWeight  Float
  recommendedRepsLo  Int
  recommendedRepsHi  Int
  recommendedRir     Int
  confidence         Float
  actualWeight       Float?
  actualReps         Int?
  actualRir          Int?
  completedAt        DateTime?
  @@index([exerciseId, completedAt])
}
````

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
# spin up full stack
make dev

# run linters
make lint      # eslint + ruff

# run tests
make test      # jest + pytest

# DB migration (dev)
pnpm db:migrate:dev

# gRPC stubs regen
make proto
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

| Package                    | Purpose                  |
| -------------------------- | ------------------------ |
| **node** 18 LTS            | API & web runtime        |
| **pnpm** 9.x               | Monorepo package manager |
| **react** 19.x             | Front-end                |
| **zustand** 4.x            | State management         |
| **tailwindcss** 4.x        | Styles                   |
| **express / fastify** 4    | API server               |
| **prisma** 5.x             | ORM                      |
| **grpc-tools** 1.63        | Proto codegen            |
| **python** 3.11            | ML engine                |
| **pytorch-lightning** 2    | Training loop            |
| **pyro-ppl** 1.x           | Bayesian layers          |
| **structlog** 24           | JSON logs                |
| **ruff** 0.4               | Python linter            |
| **jest** 30 / **pytest** 8 | Tests (TS / Py)          |
| **open-telemetry** 1.26    | Tracing                  |
| **sentry-sdk** 2.0         | Error tracking           |
| **aws-cli / boto3**        | S3 model store           |

---

## 12 · Next Steps

1. **Clone repo**, create `.env`, run `make dev`.
2. Implement **Phase 0** migrations → `pnpm db:generate`.
3. Smoke‐test `POST /recommendation` with sample history (script in `scripts/demo.py`).
4. Keep `ROADMAP.md` in sync—bots rely on task IDs.

*Specification complete – further questions should be answerable by this document or existing meta-files.* 💪

```


