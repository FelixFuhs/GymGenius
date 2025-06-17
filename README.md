---
name:        GymGenius
tagline:     "The AI-Powered Adaptive Training System That Thinks So You Don\'t Have To"
version:     0.2.0
phase:       beta
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
| ![phase](https://img.shields.io/badge/Phase-Beta-yellow) | Current roadmap phase |

## Table of Contents
1. [Why GymGenius?](#why-gymgenius)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [Tech Stack](#tech-stack)
5. [Contributing](#contributing)
6. [Roadmap](#roadmap)
7. [Community & Support](#community--support)
8. [License](#license)
9. [Staging Compose](#staging-compose)

### Why GymGenius?

* **Zero Thinking** – automatic load, rep, and rest prescriptions
* **Evidence-Based** – mechanical-tension & volume-landmarks baked in
* **Truly Adaptive** – learns your recovery τ and RIR bias every session

### Quick Start

```bash
# 1 Clone and enter repo
git clone https://github.com/your-org/gymgenius.git
cd gymgenius

# 1.1 Configure environment variables
cp .env.example .env  # then fill in JWT and Postgres settings (see Environment Variables section)

# 2 Spin up full stack (API + DB + Web)
make dev            # alias for `docker compose up --build`

# 3 Set up the database (Run these in a separate terminal after 'make dev' has started the DB)
# Ensure the 'db' service is running before executing these:
docker compose exec engine python database/create_schema.py
docker compose exec engine python database/seed_data.py # For initial exercise list, etc.

# 4 Visit the app
open http://localhost:8000
```

> **Prerequisites**: Docker ≥ 24, Python 3.11, Make, GNU Bash (macOS/Linux) or WSL 2 (Windows), Redis (for background worker functionality).

To process background training jobs, such as updating user analytics or running machine learning model updates, GymGenius uses a separate worker process. This worker relies on Redis for task queuing.

**Important:** Ensure you have a Redis server running and accessible to the `engine` service for the worker to function correctly. (Instructions for adding Redis to the local `docker-compose` setup will be part of the setup improvements - Step 2 of the plan).

Once Redis is available, run the worker in a separate terminal:
```bash
docker compose exec engine python -m engine.worker
```
Alternatively, if you are running the engine service outside of Docker locally (e.g. for debugging) and have your Python environment set up, you can run:
```bash
python -m engine.worker
```

### Environment Variables

The API requires several settings to run. Copy `.env.example` to `.env` and provide values for:

- `JWT_SECRET_KEY`
- `DATABASE_URL` *(optional)* or `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

### Project Structure

| Path                   | Purpose                                      |
| ---------------------- | -------------------------------------------- |
| `/webapp/`             | Vanilla JS + HTML PWA                        |
| `/engine/`             | Flask API with adaptive logic                |
| `/database/`           | SQL schema & seed scripts                    |
| `/tests/`              | Unit tests                                   |
| `/infrastructure/`     | Deployment configs                           |
| `docker-compose.yml`   | Local dev stack                              |

### Tech Stack

* **Frontend**: Vanilla JavaScript + HTML, Service Worker
* **Backend**: Python 3.11, Flask, PostgreSQL 13
* **ML Logic**: Integrated into the Flask service
* **DevOps**: Docker Compose, GitHub Actions; AWS ECS planned for Phase 4
* **Observability**: Sentry, Datadog, OpenTelemetry traces

> Full dependency matrix lives in **[`TECH_STACK.md`](TECH_STACK.md)**.

### Contributing

1. Read **[`AGENT_GUIDE.md`](AGENT_GUIDE.md)** if you are an autonomous coding agent.
2. Humans: see **[`CONTRIBUTING.md`](CONTRIBUTING.md)** for branch naming, commit style, and PR checklist.
3. Run `make lint && make test` before every PR.

### Roadmap

The current roadmap lives in **[`ROADMAP.md`](ROADMAP.md)**. High-level phases:

| Phase | Key Outcome                                        |
| ----- | -------------------------------------------------- |
| Alpha | Internal dog-food; core logging loop works         |
| Beta  | 50-100 private users; adaptive engine v1 validated |
| v1    | Public launch; plan templates, plateau detection   |
| v2    | Marketplace & social features                      |

### Community & Support

* Discord: `https://discord.gg/gymgenius` – real-time chat
* Discussions: GitHub → **Discussions** tab
* Found a bug? Open an Issue with a reproducible snippet.

### License

Distributed under the **MIT License** – see **[`LICENSE.md`](LICENSE.md)** for full text.

### Staging Compose

For a local mock of the AWS stack, follow the steps in **[`infrastructure/aws/README.md`](infrastructure/aws/README.md#running-the-staging-compose-file-locally)**.
