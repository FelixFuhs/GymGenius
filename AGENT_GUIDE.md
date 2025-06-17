# Agent Guide 🤖

> **Scope** These rules apply to any automated contributor (Jules, GitHub Copilot, OpenAI Codex, etc.).
> Humans should follow the standard CONTRIBUTING.md.

## 1 Auth & Identity

* **Git user.email** must contain the agent name (e.g., `jules-bot@gymgenius.ai`).
* Each commit must add the trailer `Signed-off-by: Agent <agent@domain>`.

## 2 Branch & PR Protocol

| Rule | Example |
|------|---------|
| Branch name | `<task-ID>/<agent>` → `P1-BE-001/jules` |
| Base branch | always `main` |
| PR title | `[P1-BE-001] Describe action` |
| Max LOC per PR | **400** changed lines |
| CI status | must be green (`lint`, `test`, `docker-build`) |

## 3 Coding Rules

**Note:** Some tools and commands mentioned (e.g., `pnpm db:migrate:dev`) relate to a different or future tech stack (Node.js, Prisma). For the current Python/Flask backend and VanillaJS frontend, refer to the `Makefile` and standard practices for those technologies.

* Run `make lint` → eslint/prettier must pass.
* Generate code **inside the correct workspace path**; never touch `/node_modules`.
* Follow folder mapping from `ARCHITECTURE.md` JSON.
* All TypeScript must use `strict` mode; all Python must pass `ruff` linter.
* If updating schema, also run `pnpm db:migrate:dev` and commit the SQL migration.

## 4 Commit Message Convention

```
<type>(<scope>): <summary>  # type = feat | fix | refactor | chore | test

Body: *optional*, wrap at 72 chars.
Footer: “refs #<issue>” or “closes #<issue>”.
```

* Agents **must** include the task-ID in `<scope>` (e.g., `feat(api): P1-BE-001 add /v1/predict`).

## 5 Safety & Guardrails

* **NEVER** expose secrets—use `.env.example` keys only.
* Load jumps: algorithm code must cap any single weight change to ±7.5 %.
* Schema updates require a data-migration script or must be backward-compatible.
* If CI warns “large diff” (> 400 LOC) → split into smaller PRs.

## 6 Task Lifecycle (for planners)

1. Agent reads open boxes in `ROADMAP.md`.
2. Creates branch + draft PR with WIP prefix.
3. Pushes commits, triggering CI.
4. After green, removes WIP, assigns human reviewer.
5. Merge when at least **one human** approves.

## 7 Allowed & Forbidden Tools

| Allowed | Forbidden |
|---------|-----------|
| `pnpm`, `docker`, `pytest`, `jest`, `ruff` | Direct DB writes in prod, `--force` git pushes to `main` |

## 8 Self-Termination Clause

If an agent detects an unresolvable merge conflict or CI red > 3 runs, it must:

1. Post a comment tagging `@maintainers`.
2. Close its own PR with status `blocked`.
3. Await human intervention.

---

Happy coding 🤖
