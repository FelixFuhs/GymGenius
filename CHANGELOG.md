# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial database schema definition script (`database/create_schema.py`) for PostgreSQL.
  - Includes tables: `users`, `exercises`, `workout_plans`, `plan_days`, `plan_exercises`, `workouts`, `workout_sets`, `estimated_1rm_history`, `muscle_recovery_patterns`, `plateau_events`.
  - Includes basic indexing for performance.
- Initial data seeding script (`database/seed_data.py`) for the `exercises` table.
  - Populates the table with a diverse set of common exercises.
