# Frontend

The underwriter UI: React + TypeScript (Vite), shadcn/ui + Tailwind, react-router, axios.

## Run

```bash
cp .env.example .env    # set VITE_APPLICANT_ID
npm install
npm run dev             # http://localhost:5174 — the backend must run on :8001
```

Vite proxies the API paths (`/documents`, `/health`) to the backend; see `vite.config.ts`.

## Layout

```
src/
├── api/          axios client + one module per backend resource (documents.ts)
├── hooks/        data hooks (useDocuments: list + upload for any kind of document)
├── components/   feature components (documents/) and shadcn/ui primitives (ui/)
├── pages/        Layout (header + menu), ApplicantPage, RequirementsPage
└── config.ts     upload rules mirrored from the backend, and the applicant from .env
```
