---
file: CONTRIBUTING.md
purpose: Human contribution guide (AIs see AGENT_GUIDE.md)
updated: 2025-06-14
---

# Contributing to **GymGenius** 🏋️‍♀️

Thank you for considering a contribution! Whether you're fixing a typo, building a feature, or hardening the ML engine, we welcome PRs of all sizes.

## 1 — Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node | ≥ 18.x  | <https://nodejs.org> |
| pnpm | ≥ 9.x   | `npm i -g pnpm` |
| Python | 3.11  | <https://python.org> |
| Docker | ≥ 24  | <https://docker.com> |

Clone the repo and start the dev stack:

```bash
git clone https://github.com/your-org/gymgenius.git
cd gymgenius
make dev      # docker compose up --build
```

## 2 — Issue & Feature Workflow

1. **Search first** – avoid duplicates.
2. Open an **Issue** using the correct template:
   * 🐞 Bug report
   * 💡 Feature request
3. A maintainer will triage and assign a *task-ID* (see `ROADMAP.md`).
4. Create a branch: `git checkout -b P2-FE-002/new-tooltip`.

## 3 — Branch & Commit Conventions

| Convention | Example |
| ---------- | ------------------------------------------------------------------ |
| Branch     | `P<phase>-<area>-NNN/<short-desc>`<br>`P1-BE-001/add-login` |
| Commit     | Conventional Commits + task-ID in scope:<br>`feat(api): P1-BE-003 add refresh tokens` |

**Commit structure**

```
<type>(<scope>): <summary>

Body (wrapped at 72 chars).

Refs: #<issue-number>
```

*Allowed* types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.

## 4 — Code Style & Tooling

| Language     | Formatter       | Linter          | Command          |
| ------------ | --------------- | --------------- | ---------------- |
| TypeScript   | Prettier        | ESLint (Airbnb) | `make lint-ts`   |
| Python       | Ruff (pep8)     | Ruff            | `make lint-py`   |
| SQL (Prisma) | `prisma format` | —               | `pnpm db:format` |

* Breaking lint rules blocks CI.
* Do **not** commit with warnings suppressed via `// eslint-disable`. Fix the root cause.

## 5 — Tests & Coverage

| Stack   | Runner               | Min Coverage |
| ------- | -------------------- | ------------ |
| TS/Node | Jest                 | 80 % lines   |
| Python  | Pytest + Coverage.py | 80 % lines   |

Run locally:

```bash
make test       # runs both jest & pytest
```

PRs failing to meet coverage will not pass CI unless tagged `#skip-cov` by a maintainer.

## 6 — Database Migrations

1. Modify the Prisma schema.
2. Run `pnpm db:migrate:dev` – this creates a timestamped SQL file in `/database/migrations/`.
3. Commit both the schema **and** the SQL file.
4. Update seed scripts if necessary.

Migrations **must** be backward-compatible until a major version bump.

## 7 — Pull-Request Checklist

* [ ] Task-ID present in branch name and PR title
* [ ] `make lint && make test` green locally
* [ ] Code formatted (Prettier / Ruff)
* [ ] Added or updated unit tests
* [ ] Docs or comments updated (if user-facing change)
* [ ] No secrets, hard-coded tokens, or personal data in diff
* [ ] PR size ≤ 400 LOC (or justified in description)

Two approvals required (one may be from an automation account).

## 8 — Release Flow

1. Maintainer merges PRs → `main`.
2. When roadmap exit criteria met, create GitHub Release `vX.Y.Z` *(SemVer)*.
3. GitHub Actions tags Docker images and deploys to **staging**; smoke tests run.
4. Manual promotion → **production** with `gh workflow run deploy-prod`.

## 9 — Code of Conduct

All participants must abide by the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md).

## 10 — Security & Disclosure

* Found a vulnerability? Email **[security@gymgenius.app](mailto:security@gymgenius.app)** or DM `@maintainers` on Discord.
* Please **do not** open GitHub Issues for security matters.
* We follow a 90-day public disclosure window.

Happy lifting & coding! 💪
