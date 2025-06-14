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
