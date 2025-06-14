---
name:        GymGenius
tagline:     "The AI-Powered Adaptive Training System That Thinks So You Don\'t Have To"
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

## Table of Contents
1. [Why GymGenius?](#why-gymgenius)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [Tech Stack](#tech-stack)
5. [Contributing](#contributing)
6. [Roadmap](#roadmap)
7. [Community & Support](#community--support)
8. [License](#license)

### Why GymGenius?

* **Zero Thinking** – automatic load, rep, and rest prescriptions
* **Evidence-Based** – mechanical-tension & volume-landmarks baked in
* **Truly Adaptive** – learns your recovery τ and RIR bias every session

### Quick Start

```bash
# 1 Clone and enter repo
git clone https://github.com/your-org/gymgenius.git
cd gymgenius

# 2 Spin up full stack (API + DB + ML worker + Web)
make dev            # alias for `docker compose -f docker-compose.dev.yml up --build`

# 3 Visit the app
open http://localhost:3000
```

> **Prerequisites**: Docker ≥ 24, Node 18 LTS, Make, GNU Bash (macOS/Linux) or WSL 2 (Windows).

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

### Tech Stack

* **Frontend**: React + TypeScript + Vite, Zustand state, Tailwind UI
* **Backend**: Node 18, Express / Fastify, PostgreSQL 16, Redis 7
* **ML Service**: Python 3.11, PyTorch 2.3, FastAPI, pydantic
* **DevOps**: Docker, GitHub Actions, Terraform + AWS ECS (prod)
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
