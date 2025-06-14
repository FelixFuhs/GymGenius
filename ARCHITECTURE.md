Below are the **next two meta-docs**—ready to drop into the repo root.
(If you’d rather get **CONTRIBUTING.md** and **LICENSE.md** now as well, just say the word.)

---

## `ARCHITECTURE.md`

````markdown
# GymGenius — System Architecture

> Last updated: 2025-06-14

---

## 1 Bird-Eye Diagram

```mermaid
flowchart LR
    subgraph Client
        A[Web PWA<br/>React + TS]
    end
    subgraph AWS ECS Cluster
        B(API Service<br/>Node 18)
        C(ML Engine<br/>Python 3.11)
        D(Job Worker<br/>Bull Queue)
    end
    subgraph Data Layer
        E[(PostgreSQL 16)]
        F[(Redis 7)]
        G[(S3 Model Store)]
    end

    A -- REST/JSON --> B
    B -- gRPC --> C
    B <-- Redis Pub/Sub --> D
    B -- SQL --> E
    C -- SQL (read-only) --> E
    C -- store ckpt --> G
````

---

## 2 Service Registry (machine-readable)

```jsonc
{
  "services": [
    {
      "name": "web",
      "path": "apps/web",
      "lang": "typescript",
      "port": 3000,
      "depends_on": ["api"]
    },
    {
      "name": "api",
      "path": "apps/api",
      "lang": "typescript",
      "port": 4000,
      "depends_on": ["postgres", "redis", "engine"]
    },
    {
      "name": "engine",
      "path": "services/engine",
      "lang": "python",
      "port": 5000,
      "depends_on": ["postgres", "s3"]
    },
    {
      "name": "worker",
      "path": "services/worker",
      "lang": "typescript",
      "queue": "bull",
      "depends_on": ["redis", "postgres"]
    }
  ],
  "datastores": [
    { "name": "postgres", "type": "sql", "image": "postgres:16" },
    { "name": "redis", "type": "cache", "image": "redis:7" },
    { "name": "s3", "type": "object_storage", "provider": "aws" }
  ]
}
```

Agents can parse this JSON to auto-map folder names to Docker services.

---

## 3 Data-Flow Cheat-Sheet

| Path              | Payload                          | Notes                 |
| ----------------- | -------------------------------- | --------------------- |
| `web → api`       | REST/JSON (`/workouts`, `/sets`) | JWT auth              |
| `api → engine`    | gRPC (`PredictSet` req/resp)     | \~5 ms avg            |
| `api ⇆ redis`     | Pub/Sub `workout_logged`         | Triggers worker jobs  |
| `worker → engine` | CLI `train.py --days=1`          | Nightly fine-tune     |
| `engine → s3`     | `model-{date}.pth`               | Versioned checkpoints |
| `api → postgres`  | CRUD                             | Prisma ORM            |

---

## 4 Key Tech Decisions (TDR links)

* **Monorepo** (`pnpm workspace`) until MAU > 50 k → TDR-001
* **Postgres** over Mongo for relational complexity → TDR-002
* **Redis** chosen for both cache and queue broker → TDR-003
* **Docker Compose** in dev; ECS Fargate in prod → TDR-004

(TDR docs live in `docs/tdr/`.)

---

## 5 Runtime Envs

| Environment | URL                             | Authentication   | Deploy Trigger      |
| ----------- | ------------------------------- | ---------------- | ------------------- |
| Local       | `localhost:*`                   | none             | `make dev`          |
| Staging     | `https://staging.gymgenius.app` | Auth0 dev tenant | Merge → `main`      |
| Production  | `https://app.gymgenius.app`     | Auth0 prod       | GitHub Release `v*` |

---

## 6 Scaling Plan

1. **Vertical**: bump ECS task CPU/RAM (target P99 < 150 ms).
2. **Read Replicas**: Postgres --> Aurora Serverless v2.
3. **Service Split**: if `engine` CPU > 70 %, move to GPU node pool.

---

*End of file*

````

---

## `AGENT_GUIDE.md`  *(rules for autonomous coding agents)*

```markdown
# Agent Guide 🤖

> **Scope** These rules apply to any automated contributor (Jules, GitHub Copilot, OpenAI Codex, etc.).  
> Humans should follow the standard CONTRIBUTING.md.

---

## 1 Auth & Identity

* **Git user.email** must contain the agent name (e.g., `jules-bot@gymgenius.ai`).  
* Each commit must add the trailer `Signed-off-by: Agent <agent@domain>`.

---

## 2 Branch & PR Protocol

| Rule | Example |
|------|---------|
| Branch name | `<task-ID>/<agent>` → `P1-BE-001/jules` |
| Base branch | always `main` |
| PR title | `[P1-BE-001] Describe action` |
| Max LOC per PR | **400** changed lines |
| CI status | must be green (`lint`, `test`, `docker-build`) |

---

## 3 Coding Rules

* Run `make lint` → eslint/prettier must pass.  
* Generate code **inside the correct workspace path**; never touch `/node_modules`.  
* Follow folder mapping from `ARCHITECTURE.md` JSON.  
* All TypeScript must use `strict` mode; all Python must pass `ruff` linter.  
* If updating schema, also run `pnpm db:migrate:dev` and commit the SQL migration.

---

## 4 Commit Message Convention

````

<type>(<scope>): <summary>  # type = feat | fix | refactor | chore | test

Body: *optional*, wrap at 72 chars.
Footer: “refs #<issue>” or “closes #<issue>”.

```

* Agents **must** include the task-ID in `<scope>` (e.g., `feat(api): P1-BE-001 add /v1/predict`).

---

## 5 Safety & Guardrails

* **NEVER** expose secrets—use `.env.example` keys only.  
* Load jumps: algorithm code must cap any single weight change to ±7.5 %.  
* Schema updates require a data-migration script or must be backward-compatible.  
* If CI warns “large diff” (> 400 LOC) → split into smaller PRs.

---

## 6 Task Lifecycle (for planners)

1. Agent reads open boxes in `ROADMAP.md`.  
2. Creates branch + draft PR with WIP prefix.  
3. Pushes commits, triggering CI.  
4. After green, removes WIP, assigns human reviewer.  
5. Merge when at least **one human** approves.

---

## 7 Allowed & Forbidden Tools

| Allowed | Forbidden |
|---------|-----------|
| `pnpm`, `docker`, `pytest`, `jest`, `ruff` | Direct DB writes in prod, `--force` git pushes to `main` |

---

## 8 Self-Termination Clause

If an agent detects an unresolvable merge conflict or CI red > 3 runs, it must:

1. Post a comment tagging `@maintainers`.  
2. Close its own PR with status `blocked`.  
3. Await human intervention.

---

Happy coding 🤖
```

---

**Let me know** when you’re ready for the last two docs—`CONTRIBUTING.md` and `LICENSE.md`—or if you want tweaks to these!
