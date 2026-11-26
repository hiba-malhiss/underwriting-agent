# Underwriting Agent — working rules

A health insurance eligibility-screening demo on Azure (Blob Storage, AI Search, Foundry, Document
Intelligence). It **recommends**; an underwriter **decides**. Synthetic data only — never real
customer or patient data.

## Backend architecture (`backend/app/`)

```
core/            settings, base errors (AppError), global error handler, small helpers
infrastructure/  everything that talks to Azure (credential, storage/, later search/, …)
<feature>/       one package per feature, same layout: controller, service, dependencies,
                 schemas, plus feature files (types, validation, …)
main.py          composition root only: shared clients + module wiring
```

- **A big feature splits by responsibility inside its own folder**, only when it really has many
  files (`documents/` stays flat). `rules/`: controller, service, dependencies, schemas at its
  root, then `domain/` (format, checks, evaluator: no LLM, no database), `generation/` (LLM
  prompts, extraction steps, repair loop) and `persistence/` (repository, tables). `domain/`
  imports neither of the other two.
- **Dependency rule:** `feature → infrastructure → core`. `core` imports no app module;
  `infrastructure` imports no feature.
- **Controller** = HTTP only. **Service** = business rules, plain Python (no FastAPI, no settings).
  **dependencies.py** = the `Depends` wiring and building the module's clients.
- **Errors:** raise exceptions that subclass `core.errors.AppError` (they carry their status
  code). No `try/except` in routes; `core/error_handlers.py` answers them all.
- **Abstractions:** add an interface (Protocol) only when there are two real implementations. A
  test fake alone is not a reason: type with the concrete class and pass fakes in tests. No
  layers that only forward calls.
- **Azure sign-in:** one shared credential (`infrastructure/azure_credential.py`). No keys or
  secrets in code; Managed Identity on Azure, browser sign-in locally.

## Frontend (`frontend/`)

Vite + React + TypeScript, shadcn/ui + Tailwind, react-router, axios, TanStack Query.
`components/<area>/<Component>/`, `pages/`.

- **`api/<resource>.ts`, one module per backend resource:** the axios calls **and** all its
  TanStack Query code (query keys, `useXQuery`, `useXMutation`), so any component can reuse them.
  No separate `hooks/` folder for server data.
- Mutations invalidate the related query keys in `onSuccess` (return the promise, so
  `mutateAsync` resolves after the refetch). Components call `mutateAsync` in `try/catch` and show
  the toast; the api module shows no UI.
Page paths must never start with an API path that Vite proxies (or a refresh hits the backend).

## Plan

`docs/PLAN.md` is the build plan: the steps from scratch, per version (v1 / v2 / v3). Read it
before starting work. It holds no progress; keep it a plan (update it when the plan changes).

## Working style

- Go step by step; explain each step. Read a file before changing it — the user edits often.
- Don't change Azure resources without asking first. Read-only checks are fine; list anything
  changed.
- Before finishing: `ruff format`, `ruff check`, `pytest` (backend); `npm run build` (frontend).
- Commit only when asked. Short commit message. Never add a Co-Authored-By line.
