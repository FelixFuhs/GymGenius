# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Addressed missing Redis dependency for the background worker (`engine.worker`) by adding a Redis service to `docker-compose.yml` and updating documentation.
- Corrected a critical Nginx proxy configuration issue by adding `webapp/default.conf` and updating `docker-compose.yml` to ensure the frontend can communicate with the backend API.
- Fixed a bug in `webapp/js/app.js` where `set_number` was hardcoded, preventing correct logging of multiple sets for an exercise. Implemented dynamic set number tracking.
- Improved local development setup instructions in `README.md` and created a comprehensive `HOW_TO_USE.md`.

### Changed
- Updated `ARCHITECTURE.md` and partially updated `TECHNICAL_SPEC.md` to better reflect the current tech stack (VanillaJS, Python/Flask, Redis) and acknowledge discrepancies with prior documentation.

### Added
- **P2-INF-004**: Documented conceptual setup for a staging environment on AWS ECS + RDS in `infrastructure/aws/README.md` and provided an illustrative `docker-compose.staging.yml`.
- **P2-PM-005**: Drafted beta feedback survey questions and a KPI dashboard outline in `PRODUCT_FEEDBACK.md`.

### Changed
- **P1-PM-007**: Updated `ROADMAP.md` checkbox to mark the 10-user cohort as complete, matching `TODO.md`.

## [0.2.0] - 2024-08-02 - Phase 2 Beta Features

### Added
- **P1-BE-001 (Rectified)**: Enhanced database schema (`database/create_schema.py`) to align with Project Vision specifications, including usage of UUIDs for primary keys, JSONB for flexible data storage, and detailed table structures. Updated `seed_data.py` for compatibility and added `main_target_muscle_group` to the `exercises` table to support fatigue modeling. Ensured scripts are executable within a Dockerized PostgreSQL environment.
- **P2-DS-001**: Implemented core logic for RIR-bias learning and a fatigue decay model in `engine/learning_models.py`. Integrated these into `engine/app.py` with new API endpoints:
    - `POST /v1/user/<user_id>/update-rir-bias`: Updates user's RIR bias based on performance.
    - `GET /v1/user/<user_id>/fatigue-status?muscle_group=<muscle_code>`: Calculates and returns current fatigue for a given muscle group.
- **P2-FE-002**: Implemented a new recommendation endpoint `GET /v1/user/<user_id>/exercise/<exercise_id>/recommend-set-parameters` in `engine/app.py` providing weight, rep, RIR suggestions, and a detailed explanation string. Integrated this into the frontend (`webapp/js/app.js`) on the `LogSetPage` to display AI recommendations and the explanation via a "Why this weight?" tooltip (using the `title` attribute of an info icon).
- **P2-BE-003**: Added a new webhook endpoint `POST /v1/system/trigger-training-pipeline` to `engine/app.py` for simulating the initiation of nightly model-training pipelines. Includes basic request parsing and logs simulated per-user training task triggers.

## [0.1.0] - 2025-06-14 - Phase 1 Alpha

### Added
- **P1-INF-002**: Initial Docker-compose development stack and Makefile for common operations.
- **P1-FE-003**: Basic structure for Minimal PWA (Progressive Web App) including placeholder pages for login, workout list, and set logging (`webapp/`).
- **P1-DS-004**: Extended-Epley 1RM prediction formula endpoint (`/v1/predict/1rm/epley`) using Flask (`engine/`).
- **P1-FE-005**: Web form for RIR (Reps In Reserve) and weight input, with basic plate rounding logic (`webapp/js/app.js`).
- **P1-INF-006**: Initial GitHub Actions CI workflow (`.github/workflows/ci.yml`) with placeholders for linting, testing, and Docker image building.
- **P1-PM-007**: (Marked as complete as per project TODO) 10-user internal test cohort recruited.
