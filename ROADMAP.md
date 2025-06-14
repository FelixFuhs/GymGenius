# GymGenius — Product & Engineering Roadmap

> **Format rules (AI-friendly)**
> - Every task has a unique ID: `P<phase>-<area>-NNN`.
> - Area codes: `BE` backend, `FE` frontend, `DS` data-science, `INF` infra, `PM` product-mgmt.
> - Check-boxes show live status so agents can grep for " - [ ] ".

## Phase 1 — Alpha (internal dog-food)   📅 May → July 2025
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P1-BE-001** | `@api-team` | Bootstrap PostgreSQL schema (all tables from ProjectVISION) & seed data (incl. 50+ exercises). | - [x] |
| **P1-INF-002** | `@infra` | Docker-compose dev stack + Makefile | - [x] |
| **P1-FE-003** | `@web` | Minimal PWA: User auth screens (signup/login), browse exercises, log workout screen (manual entry). | - [x] |
| **P1-DS-004** | `@engine` | Implement `estimate_1rm` (Extended Epley) & `calculate_training_params` as foundation for progression. | - [x] |
| **P1-FE-005** | `@web` | RIR + weight input form with plate rounding | - [x] |
| **P1-INF-006** | `@infra` | GitHub Actions CI (lint, test, docker build) | - [x] |
| **P1-PM-007** | `@product` | 10-user internal test cohort recruited | - [ ] |
| **P1-BE-008** | `@api-team` | Implement Authentication backend (signup/login/JWT management). | - [x] |
| **P1-BE-009** | `@api-team` | Implement User Profile Management APIs (CRUD for user settings, goals, equipment). | - [x] |
| **P1-BE-010** | `@api-team` | Implement Basic CRUD APIs for Exercises (create, read, update, delete - admin initially). | - [x] |
| **P1-BE-011** | `@api-team` | Implement Basic CRUD APIs for Workout Logging (log sets, workouts). | - [x] |

**Exit criteria**
* ≥ 80 % of test lifts logged without manual weight edits
* Crash-free sessions > 98 %

## Phase 2 — Private Beta (≤ 100 users)   📅 Aug → Oct 2025
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P2-DS-001** | `@engine` | Implement core adaptive algorithm components: RIR-bias learning, fatigue tracking model (user-specific), initial weight recommendation logic. | - [ ] |
| **P2-FE-002** | `@web` | “Why this weight?” tooltip (explainable AI) | - [ ] |
| **P2-BE-003** | `@api-team` | Webhook → nightly model-training pipeline | - [ ] |
| **P2-INF-004** | `@infra` | Local staging environment via Docker Compose; AWS deployment deferred to Phase 4 (see P4-INF-011) | - [ ] |
| **P2-PM-005** | `@product` | Beta feedback survey + KPI dashboard | - [ ] |
| **P2-DS-006** | `@engine` | Implement trend detection for exercise performance. | - [ ] |
| **P2-DS-007** | `@engine` | Implement basic plateau detection (based on trend). | - [ ] |
| **P2-DS-008** | `@engine` | Implement generation of simple deload protocols. | - [ ] |
| **P2-DS-009** | `@engine` | Implement confidence scoring for weight recommendations. | - [ ] |
| **P2-FE-006** | `@web` | Frontend integration for displaying AI weight recommendations, target reps/RIR. | - [ ] |

Exit criteria: **day-7 retention ≥ 50 %**, MAE < 2.5 % on weight predictions.

## Phase 3 — Public v1   📅 Nov 2025 → Jan 2026
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P3-FE-001** | `@web` | Implement Plan Builder UI: drag & drop, template library, display volume/freq. | - [ ] |
| **P3-DS-002** | `@engine` | Plateau detection + auto-deload protocol | - [ ] |
| **P3-FE-003** | `@web` | Analytics Dashboard UI: 1RM evolution, strength curves, volume heatmaps, trend display. | - [ ] |
| **P3-INF-004** | `@infra` | Observability stack (Datadog, OpenTelemetry) | - [ ] |
| **P3-PM-005** | `@product` | Freemium pricing & subscription flow | - [ ] |
| **P3-BE-006** | `@api-team` | Backend for Plan Builder: Save/load plans, volume/frequency calcs, flexible scheduling logic. | - [ ] |
| **P3-DS-003** | `@engine` | Algorithm for exercise selection recommendations within plan builder. | - [ ] |
| **P3-BE-007** | `@api-team` | Backend for Analytics: Data aggregation for dashboard visualizations. | - [ ] |
| **P3-FE-004** | `@web` | Implement UI for achievement system. | - [ ] |
| **P3-BE-008** | `@api-team` | Backend for achievement system trigger logic. | - [ ] |
| **P3-PM-006** | `@product` | Define and implement exportable report formats (e.g., CSV, PDF). | - [ ] |


Exit criteria: **1 k monthly active lifters**, churn < 5 % / month.

## Phase 4 — Polish & Scale 📅 [Date TBD]
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P4-BE-001** | `@api-team` | Optimize database queries and implement caching layer (e.g., Redis). | - [ ] |
| **P4-INF-002** | `@infra` | Enhance comprehensive error handling and monitoring setup (Sentry, Datadog). | - [ ] |
| **P4-QA-003** | `@qa` | Develop comprehensive unit and integration test suites (target >80% coverage). | - [ ] |
| **P4-INF-004** | `@infra` | Perform load testing and identify/address bottlenecks. | - [ ] |
| **P4-SEC-005** | `@sec` | Conduct security audit and address vulnerabilities. | - [ ] |
| **P4-FE-006** | `@web` | Develop user onboarding flow. | - [ ] |
| **P4-BE-007** | `@api-team` | Build admin dashboard for user management and system monitoring. | - [ ] |
| **P4-PM-008** | `@product` | Implement detailed analytics tracking (e.g., Mixpanel) for user behavior. | - [ ] |
| **P4-DOC-009** | `@product` | Create user and technical documentation. | - [ ] |
| **P4-PM-010** | `@product` | Coordinate beta testing with a larger cohort of real users. | - [ ] |
| **P4-INF-011** | `@infra` | Deploy to AWS ECS + RDS for production rollout | - [ ] |
| **P4-INF-012** | `@infra` | CI/CD pipeline to push images to ECR and update ECS services | - [ ] |

## Phase 5 — Advanced Features (Post-Launch) 📅 [Date TBD]
| ID | Owner | Description | Done |
|----|-------|-------------|------|
| **P5-PM-001** | `@product` | Program Marketplace Epic: coach uploads, revenue share. | - [ ] |
| **P5-PM-002** | `@product` | Social Layer Epic: challenges, form-check videos. | - [ ] |
| **P5-DS-003** | `@engine` | Camera-based Velocity Estimation Epic. | - [ ] |
| **P5-FE-004** | `@web` | Wearable Readiness Import Epic. | - [ ] |
| **P5-FE-005** | `@web` | Native Mobile Apps (iOS/Android) Epic. | - [ ] |
| **P5-FE-006** | `@web` | Apple Watch App Epic. | - [ ] |
| **P5-PM-007** | `@product` | Barcode Scanner for plate loading assistance Epic. | - [ ] |
| **P5-FE-008** | `@web` | Voice Commands for logging Epic. | - [ ] |
| **P5-BE-009** | `@api-team` | Export Features (PDF reports, CSV data) - if not covered in P3. | - [ ] |
| **P5-DS-010** | `@engine` | AI Form Coach (Video Analysis) Epic. | - [ ] |
| **P5-BE-011** | `@api-team` | Trainer Platform (Manage multiple clients) Epic. | - [ ] |
| **P5-BE-012** | `@api-team` | Integration Hub (MyFitnessPal, Fitbit) Epic. | - [ ] |
| **P5-DS-013** | `@engine` | Advanced Analytics (ML-powered insights) Epic. | - [ ] |

### Change-Management

* Edit this file via **pull request** only.
* Keep task IDs immutable; superseded items get a trailing `-X` suffix.
* CI fails if a phase contains unchecked tasks but has an `exit_criteria_met` flag.
