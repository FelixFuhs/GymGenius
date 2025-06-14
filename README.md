Below are **complete, copy-paste-ready drafts** for the first two meta files:

---

## `README.md`

````markdown
---
name:        GymGenius
tagline:     "The AI-Powered Adaptive Training System That Thinks So You Don’t Have To"
version:     0.1.0
phase:       alpha
license:     MIT
---

<p align="center">
  <img src="assets/logo.svg" width="180" alt="GymGenius logo"/>
</p>

> **GymGenius** is an open-source strength & hypertrophy coach that predicts the exact weight, reps, and rest you should use **in real time**, based on your own performance logs and the latest exercise-science research.

| Badge | Meaning |
|-------|---------|
| ![build](https://img.shields.io/github/actions/workflow/status/your-org/gymgenius/ci.yml) | CI status |
| ![license](https://img.shields.io/badge/License-MIT-blue.svg) | MIT license |
| ![phase](https://img.shields.io/badge/Phase-Alpha-yellow) | Current roadmap phase |

---

## Table of Contents
1. [Why GymGenius?](#why-gymgenius)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [Tech Stack](#tech-stack)
5. [Contributing](#contributing)
6. [Roadmap](#roadmap)
7. [Community & Support](#community--support)
8. [License](#license)

---

### Why GymGenius?

* **Zero Thinking** – automatic load, rep, and rest prescriptions  
* **Evidence-Based** – mechanical-tension & volume-landmarks baked in  
* **Truly Adaptive** – learns your recovery τ and RIR bias every session  

---

### Quick Start

```bash
# 1 Clone and enter repo
git clone https://github.com/your-org/gymgenius.git
cd gymgenius

# 2 Spin up full stack (API + DB + ML worker + Web)
make dev            # alias for `docker compose -f docker-compose.dev.yml up --build`

# 3 Visit the app
open http://localhost:3000
````

> **Prerequisites**: Docker ≥ 24, Node 18 LTS, Make, GNU Bash (macOS/Linux) or WSL 2 (Windows).

---

### Project Structure

| Path                   | Purpose                                      |
| ---------------------- | -------------------------------------------- |
| `/apps/web/`           | React + TypeScript PWA                       |
| `/apps/api/`           | Express (Node) REST API                      |
| `/services/engine/`    | Python micro-service (adaptive algorithm)    |
| `/packages/ui/`        | Shared design-system components              |
| `/database/`           | Prisma schema & migrations                   |
| `/docs/`               | Architecture diagrams, research white-papers |
| `docker-compose.*.yml` | Local vs CI vs prod stacks                   |

---

### Tech Stack

* **Frontend**: React + TypeScript + Vite, Zustand state, Tailwind UI
* **Backend**: Node 18, Express / Fastify, PostgreSQL 16, Redis 7
* **ML Service**: Python 3.11, PyTorch 2.3, FastAPI, pydantic
* **DevOps**: Docker, GitHub Actions, Terraform + AWS ECS (prod)
* **Observability**: Sentry, Datadog, OpenTelemetry traces

> Full dependency matrix lives in **[`TECH_STACK.md`](TECH_STACK.md)**.

---

### Contributing

1. Read **[`AGENT_GUIDE.md`](AGENT_GUIDE.md)** if you are an autonomous coding agent.
2. Humans: see **[`CONTRIBUTING.md`](CONTRIBUTING.md)** for branch naming, commit style, and PR checklist.
3. Run `make lint && make test` before every PR.

---

### Roadmap

The current roadmap lives in **[`ROADMAP.md`](ROADMAP.md)**.
High-level phases:

| Phase | Key Outcome                                        |
| ----- | -------------------------------------------------- |
| Alpha | Internal dog-food; core logging loop works         |
| Beta  | 50-100 private users; adaptive engine v1 validated |
| v1    | Public launch; plan templates, plateau detection   |
| v2    | Marketplace & social features                      |

---

### Community & Support

* Discord: `https://discord.gg/gymgenius` – real-time chat
* Discussions: GitHub → **Discussions** tab
* Found a bug? Open an Issue with a reproducible snippet.

---

### License

Distributed under the **MIT License** – see **[`LICENSE.md`](LICENSE.md)** for full text.

````

---

## `ROADMAP.md`

```markdown
# GymGenius — Product & Engineering Roadmap

> **Format rules (AI-friendly)**  
> • Every task has a unique ID: `P<phase>-<area>-NNN`.  
> • Area codes: `BE` backend, `FE` frontend, `DS` data-science, `INF` infra, `PM` product-mgmt.  
> • Check-boxes show live status so agents can grep for `" - [ ] "`.

---

## Phase 1 — Alpha (internal dog-food)   📅 May → July 2025
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P1-BE-001** | `@api-team` | Bootstrap PostgreSQL schema & seed data | - [ ] |
| **P1-INF-002** | `@infra` | Docker-compose dev stack + Makefile | - [ ] |
| **P1-FE-003** | `@web` | Minimal PWA: login → workout list → log set | - [ ] |
| **P1-DS-004** | `@engine` | Extended-Epley 1RM endpoint (`/v1/predict`) | - [ ] |
| **P1-FE-005** | `@web` | RIR + weight input form with plate rounding | - [ ] |
| **P1-INF-006** | `@infra` | GitHub Actions CI (lint, test, docker build) | - [ ] |
| **P1-PM-007** | `@product` | 10-user internal test cohort recruited | - [ ] |

**Exit criteria**  
* ≥ 80 % of test lifts logged without manual weight edits  
* Crash-free sessions > 98 %

---

## Phase 2 — Private Beta (≤ 100 users)   📅 Aug → Oct 2025
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P2-DS-001** | `@engine` | RIR-bias learning + fatigue decay model | - [ ] |
| **P2-FE-002** | `@web` | “Why this weight?” tooltip (explainable AI) | - [ ] |
| **P2-BE-003** | `@api-team` | Webhook → nightly model-training pipeline | - [ ] |
| **P2-INF-004** | `@infra` | Staging environment (AWS ECS + RDS) | - [ ] |
| **P2-PM-005** | `@product` | Beta feedback survey + KPI dashboard | - [ ] |

Exit criteria: **day-7 retention ≥ 50 %**, MAE < 2.5 % on weight predictions.

---

## Phase 3 — Public v1   📅 Nov 2025 → Jan 2026
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P3-FE-001** | `@web` | Plan template library & floating rest days | - [ ] |
| **P3-DS-002** | `@engine` | Plateau detection + auto-deload protocol | - [ ] |
| **P3-FE-003** | `@web` | Analytics dashboard (1RM graph, volume heatmap) | - [ ] |
| **P3-INF-004** | `@infra` | Observability stack (Datadog, OpenTelemetry) | - [ ] |
| **P3-PM-005** | `@product` | Freemium pricing & subscription flow | - [ ] |

Exit criteria: **1 k monthly active lifters**, churn < 5 % / month.

---

## Phase 4 — v2+ (Community & Marketplace)   📅 TBD 2026
High-level epics (details will be added closer to start date):

* **Program Marketplace** – coach uploads, revenue share  
* **Social Layer** – challenges, form-check videos  
* **Camera-based Velocity Estimation** – optional phone capture  
* **Wearable Readiness Import** – HRV & sleep auto-adjust loads  

---

### Change-Management

* Edit this file via **pull request** only.  
* Keep task IDs immutable; superseded items get a trailing `-X` suffix.  
* CI fails if a phase contains unchecked tasks but has an `exit_criteria_met` flag.

