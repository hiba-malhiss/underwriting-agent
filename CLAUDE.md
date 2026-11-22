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

- **Dependency rule:** `feature → infrastructure → core`. `core` imports no app module;
  `infrastructure` imports no feature.
- **Controller** = HTTP only. **Service** = business rules, plain Python (no FastAPI, no settings).
  **dependencies.py** = the `Depends` wiring and building the module's clients.
- **Errors:** raise exceptions that subclass `core.errors.AppError` (they carry their status
  code). No `try/except` in routes; `core/error_handlers.py` answers them all.
- **Abstractions:** add one only when it has a second user (a second implementation, a test fake,
  or a second module). No layers that only forward calls.
- **Azure sign-in:** one shared credential (`infrastructure/azure_credential.py`). No keys or
  secrets in code; Managed Identity on Azure, browser sign-in locally.

## Frontend (`frontend/`)

Vite + React + TypeScript, shadcn/ui + Tailwind, react-router, axios. `api/` one module per
backend resource, `hooks/` for data, `components/<area>/<Component>/`, `pages/`.
Page paths must never start with an API path that Vite proxies (or a refresh hits the backend).

## Working style

- Go step by step; explain each step. Read a file before changing it — the user edits often.
- Don't change Azure resources without asking first. Read-only checks are fine; list anything
  changed.
- Before finishing: `ruff format`, `ruff check`, `pytest` (backend); `npm run build` (frontend).
- Commit only when asked. Short commit message. Never add a Co-Authored-By line.
