# Todo

This file lists the next logical tasks to be done in the GymGenius project.

## Phase 1 - Alpha (internal dog-food)

- [x] **P1-INF-002**: `@infra` Docker-compose dev stack + Makefile
- [x] **P1-FE-003**: `@web` Minimal PWA: login → workout list → log set
- [x] **P1-DS-004**: `@engine` Extended-Epley 1RM endpoint (`/v1/predict`)
- [x] **P1-FE-005**: `@web` RIR + weight input form with plate rounding
- [x] **P1-INF-006**: `@infra` GitHub Actions CI (lint, test, docker build)
- [x] **P1-PM-007**: `@product` 10-user internal test cohort recruited

## Phase 2 - Private Beta (≤ 100 users)

- [x] **P2-DS-001**: `@engine` RIR-bias learning + fatigue decay model
- [x] **P2-FE-002**: `@web` “Why this weight?” tooltip (explainable AI)
- [x] **P2-BE-003**: `@api-team` Webhook → nightly model-training pipeline
- [x] **P2-INF-004**: `@infra` Staging environment (AWS ECS + RDS) - (_Documentation for setup and conceptual `docker-compose.staging.yml` created in `infrastructure/aws/`_)
- [x] **P2-PM-005**: `@product` Beta feedback survey + KPI dashboard - (_Draft survey questions and KPI dashboard outline created in `PRODUCT_FEEDBACK.md`_)

## Phase 3 - Public v1

- **P3-FE-001**: `@web` Plan template library & floating rest days
- **P3-DS-002**: `@engine` Plateau detection + auto-deload protocol
- **P3-FE-003**: `@web` Analytics dashboard (1RM graph, volume heatmap)
- **P3-INF-004**: `@infra` Observability stack (Datadog, OpenTelemetry)
- **P3-PM-005**: `@product` Freemium pricing & subscription flow

## Phase 4 - v2+ (Community & Marketplace)

- Program Marketplace
- Social Layer
- Camera-based Velocity Estimation
- Wearable Readiness Import
