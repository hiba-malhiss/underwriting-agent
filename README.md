# Health Insurance Underwriting Agent

An assistant for health insurance underwriters, built on Azure. It reads an application's
documents, extracts the applicant's details, checks what is missing, and finds the
underwriting rules that apply — with citations. **It never accepts or declines an
application; the underwriter decides.**

### run application:
`.venv/bin/uvicorn app.main:app --reload --port 8001`

## How the app signs in to Azure

The identity is **not** set in the code. The code only says "use whatever identity is
available where I'm running", in `backend/app/core/azure_credential.py`:

```python
return DefaultAzureCredential()   # finds the identity by itself
```

The identity is created and attached **in Azure**, on the service that runs the code.

- **Compute** (Container Apps / App Service) = where the code runs → this is where the identity lives

### In production
1. Deploy the backend to a **Container App** (compute).
2. On the Container App: **Identity → System assigned → On**. There's no link or key to copy.
3. On the **storage account**: **Access control (IAM) → Add role assignment →
   Storage Blob Data Contributor → Assign access to: Managed identity** → choose the Container App.
4. Set the app's environment variables:
   ```
   AZURE_STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net   # same as local
   STORAGE_CONTAINER=underwriting-documents
   ```
   Don't set `AZURE_INTERACTIVE_LOGIN` or `AZURE_TENANT_ID`.

`AZURE_STORAGE_ACCOUNT_URL` is the storage account's **address** (where); the Managed Identity
is **who** the app is. They're separate: the identity is never written into the URL.

`DefaultAzureCredential` finds the identity through a local token endpoint Azure provides to
the app (the `ManagedIdentityCredential` step). On a laptop that step fails, which is why the
browser sign-in exists for local development. A **user-assigned** identity also needs
`AZURE_CLIENT_ID` so the app knows which identity to use.
