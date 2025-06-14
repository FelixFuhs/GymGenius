# GymGenius — Product & Engineering Roadmap

> **Format rules (AI-friendly)**
> - Every task has a unique ID: `P<phase>-<area>-NNN`.
> - Area codes: `BE` backend, `FE` frontend, `DS` data-science, `INF` infra, `PM` product-mgmt.
> - Check-boxes show live status so agents can grep for " - [ ] ".

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

## Phase 2 — Private Beta (≤ 100 users)   📅 Aug → Oct 2025
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P2-DS-001** | `@engine` | RIR-bias learning + fatigue decay model | - [ ] |
| **P2-FE-002** | `@web` | “Why this weight?” tooltip (explainable AI) | - [ ] |
| **P2-BE-003** | `@api-team` | Webhook → nightly model-training pipeline | - [ ] |
| **P2-INF-004** | `@infra` | Staging environment (AWS ECS + RDS) | - [ ] |
| **P2-PM-005** | `@product` | Beta feedback survey + KPI dashboard | - [ ] |

Exit criteria: **day-7 retention ≥ 50 %**, MAE < 2.5 % on weight predictions.

## Phase 3 — Public v1   📅 Nov 2025 → Jan 2026
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P3-FE-001** | `@web` | Plan template library & floating rest days | - [ ] |
| **P3-DS-002** | `@engine` | Plateau detection + auto-deload protocol | - [ ] |
| **P3-FE-003** | `@web` | Analytics dashboard (1RM graph, volume heatmap) | - [ ] |
| **P3-INF-004** | `@infra` | Observability stack (Datadog, OpenTelemetry) | - [ ] |
| **P3-PM-005** | `@product` | Freemium pricing & subscription flow | - [ ] |

Exit criteria: **1 k monthly active lifters**, churn < 5 % / month.

## Phase 4 — v2+ (Community & Marketplace)   📅 TBD 2026
High-level epics (details will be added closer to start date):

* **Program Marketplace** – coach uploads, revenue share
* **Social Layer** – challenges, form-check videos
* **Camera-based Velocity Estimation** – optional phone capture
* **Wearable Readiness Import** – HRV & sleep auto-adjust loads

### Change-Management

* Edit this file via **pull request** only.
* Keep task IDs immutable; superseded items get a trailing `-X` suffix.
* CI fails if a phase contains unchecked tasks but has an `exit_criteria_met` flag.
