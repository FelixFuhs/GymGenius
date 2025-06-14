# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-06-14 - Phase 1 Alpha

### Added
- **P1-INF-002**: Initial Docker-compose development stack and Makefile for common operations.
- **P1-FE-003**: Basic structure for Minimal PWA (Progressive Web App) including placeholder pages for login, workout list, and set logging (`webapp/`).
- **P1-DS-004**: Extended-Epley 1RM prediction formula endpoint (`/v1/predict/1rm/epley`) using Flask (`engine/`).
- **P1-FE-005**: Web form for RIR (Reps In Reserve) and weight input, with basic plate rounding logic (`webapp/js/app.js`).
- **P1-INF-006**: Initial GitHub Actions CI workflow (`.github/workflows/ci.yml`) with placeholders for linting, testing, and Docker image building.
- **P1-PM-007**: (Marked as complete as per project TODO) 10-user internal test cohort recruited.

## [Unreleased]

### Added
- Initial database schema definition script (`database/create_schema.py`) for PostgreSQL.
  - Includes tables: `users`, `exercises`, `workout_plans`, `plan_days`, `plan_exercises`, `workouts`, `workout_sets`, `estimated_1rm_history`, `muscle_recovery_patterns`, `plateau_events`.
  - Includes basic indexing for performance.
- Initial data seeding script (`database/seed_data.py`) for the `exercises` table.
  - Populates the table with a diverse set of common exercises.
