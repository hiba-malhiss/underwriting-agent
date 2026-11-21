# Azure map — how everything connects

## Hierarchy

```
Microsoft Entra Tenant  ── the company's identities (who people and apps are)
│  Users ........ sara@…, underwriter1@…
│  Groups ....... grp-ai-developers, grp-underwriters
│  App identities  Managed Identity (the agent) · Service Principal (CI/CD)
│
└─ Management Group  (optional: groups subscriptions under shared policies)
   └─ Subscription  ── billing + permission boundary
      └─ Resource Group: rg-underwriting-dev  (everything for this app)
         │
         ├─ Storage Account ........ container: applications/  ← application PDFs   (Phase 1)
         ├─ Document Intelligence .. OCR / Layout for scanned documents          (Phase 2)
         ├─ Foundry resource                                                       (Phase 3)
         │    ├─ Deployment: chat        (writes the review)
         │    ├─ Deployment: embeddings  (text → vectors)
         │    └─ Project: underwriting   (traces + evaluations)
         ├─ AI Search .............. index: guidelines  ← underwriting rules      (Phase 4)
         ├─ MySQL Flexible Server .. applications and reviews                    (Phase 6)
         ├─ Key Vault .............. MySQL password and other secrets            (Phase 8)
         ├─ Container Apps ......... agent-api (Python)  [Managed Identity]      (Phase 8)
         ├─ App Service ............ web (Next.js)                                (Phase 7)
         ├─ VNet 10.0.0.0/16                                                     (discussed, not deployed in dev)
         │    ├─ snet-apps     10.0.1.0/24  ← the apps
         │    └─ snet-private  10.0.2.0/24  ← Private Endpoints (Search, MySQL, Storage, KV)
         └─ Log Analytics + App Insights   ← logs and monitoring                 (Phase 8)
```
