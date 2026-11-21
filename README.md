# Health Insurance Underwriting Agent

An assistant for health insurance underwriters, built on Azure. It reads an application's
documents, extracts the applicant's details, checks what is missing, and finds the
underwriting rules that apply — with citations. **It never accepts or declines an
application; the underwriter decides.**

### run application:
`.venv/bin/uvicorn app.main:app --reload --port 8001`
