# Build plan

What we're building and how, step by step from scratch.

- **Version 1 (2 days):** the core flow, end to end, running locally. For the portfolio.
- **Version 2:** make it nicer and safer.
- **Version 3:** large documents, stronger approval, and deployment.

## The idea in one paragraph

An LLM reads the underwriting **guidelines** and turns them into **parameters** (the facts
that matter, like age or BMI) and **rules** (like "age over 65 → decline"). A human checks the
rules and saves them. When someone **applies**, an LLM reads their documents and fills in the
parameter values. Then **plain code** runs the saved rules and shows the result of each rule.
**The underwriter makes the final decision.** The AI suggests; it never decides.

```
Guidelines ─► read (OCR) ─► LLM suggests parameters + rules ─► human approves ─► saved rules (version N)
                                                                                     │
Applicant docs ─► read (OCR) ─► LLM fills parameter values (with sources) ─► code runs the rules
                                                                                     │
                                                         result per rule ─► underwriter decides
```

## Who does what

| Part | Who builds it |
|---|---|
| The **shape** of a parameter and a rule, the checks, the code that runs rules | **We** (code, once) |
| The actual **parameters and rules** | The **LLM**, from the guidelines |
| Approving rules | A **human** (in the app) |
| The final accept / decline | The **underwriter** |

## Main ideas

- **Rules are data, not code.** Saved in the database as JSON, like
  `{ "param": "age", "op": ">", "value": 65 }`. The code knows the *shape* of rules, not their
  names, so new parameters work without code changes.
- **Every rule has a source:** document, page, and the exact quote. The code checks the quote
  really is in the document, so the LLM can't make one up.
- **Every applicant value has a source** too: which document and page it came from.
- **Unknown is not false.** A missing value makes the rule "unknown" (missing information),
  never a silent pass.
- **Some rules can't be code** ("at the underwriter's discretion"). They're `judgment` rules and
  always show "refer to underwriter".
- **Nothing runs until a human approves it.**

---

## Version 1: the core, in 2 days (local)

**Foundation: files**
- Resource group, Blob Storage with two containers: applicants' documents and guidelines
- Backend (FastAPI) and frontend (React + TanStack Query); sign in to Azure with your own
  account locally (browser login), no keys in code
- Upload, list and delete documents from the UI, for applicants and for guidelines

**Azure to create** (in the Portal, step by step):
- Chat model deployment in Foundry (gpt-4.1-mini)
- Document Intelligence
- MySQL Flexible Server (smallest size), Entra sign-in for your user

**Day 1: rules**
- Shapes for parameters and rules (condition and judgment), with sources; checks (known
      parameter, operator fits the type, value has the right type)
- The code that runs rules: met / not met / unknown, with a reason per rule (+ tests)
- MySQL connection and tables (created by the app at start; migrations come in v2)
- Guidelines → Document Intelligence → LLM suggests parameters + rules (strict JSON) → quote check
- **New guidelines add, they don't replace:** the LLM gets the new document **plus all the current
  parameters and rules**, and suggests **only additions**: new rules, and new parameters only if
  needed. It reuses existing parameters (`age`, not a new `applicant_age`) and skips rules that
  already exist
- Rules page: each suggested rule next to its quote, **approve / reject**, then **Save** →
  version N+1 = **all the current rules + the approved additions** (nothing is removed or changed)

**Day 2: check an applicant (nothing about the applicant is saved)**
- "Check an applicant" page: upload **all** the applicant's documents at once
- Each document → Document Intelligence → LLM fills the current version's parameters, each value
  with its source (document, page, quote). The LLM gives numbers in kg / cm directly
- Merge the documents' values: same value → two sources; different value → **flagged**
- Run the rules → the page shows each rule, the value and its source, the guideline quote, and
  "checked with rulebook version N"
- The applicant's documents and results are **not stored**: they're read, shown, and gone. Only the
  rules and parameters are saved

Processing happens in the request with a loading spinner (10–30 s per document is fine for now).

**Tables for v1** (only the rules are saved)

| Table | Main columns |
|---|---|
| `rulebook_versions` | `id`, `number`, `approved_at`, `note` |
| `parameters` | `id`, `rulebook_version_id`, `code`, `type`, `allowed_values` (JSON), `description`, `source` (JSON) |
| `rules` | `id`, `rulebook_version_id`, `code`, `kind` (condition / judgment), `when` (JSON), `outcome`, `source` (JSON) |

---

## Version 2: nicer and safer

- **Save applicants:** create an applicant (name), list them, open one; their documents in Blob
  Storage; add documents later and merge with the values already extracted
- Tables: `applicants` (`id`, `full_name`, `created_at`), `extracted_values` (`applicant_id`,
  `parameter_code`, `value`, `sources`, `conflict`), `evaluations` (`applicant_id`,
  `rulebook_version_id`, `created_at`), `rule_results`, `decisions`
- Underwriter records the decision (accept / decline / refer) with a note
- Migrations with Alembic
- Computed parameters (age from date of birth, BMI) and table rules (e.g. BMI limit by age)
- Rules page: edit a rule (not only approve / reject); new guidelines can also suggest **updating
  or deleting** existing rules (v1 only adds)
- Version history: list, view, compare two versions, go back to an old one
- Applicant status (`new` → `documents uploaded` → `values extracted` → `checked` → `decided`)
- Page to fix flagged values (conflicts, quote not found, value not in the allowed list)
- Code converts units and checks allowed values (instead of trusting the LLM)
- Missing documents from `require_document` rules
- Background processing after upload (status + auto refresh in the UI)
- Results marked **out of date** when a document or value changes; run the rules again
- Judgment rules: the LLM gives its view with the quote (still sent to a human)
- Test applicants and a coverage check (guideline parts no rule quotes)

## Version 3: bigger documents, stronger approval, deployment

- **Search index for documents:** AI Search index + indexer per container (chunks + vectors),
      hourly schedule, deletion tracking, re-index right after upload / delete
- **Large documents:** split big PDFs into chunks and search for the parts that matter (AI
      Search), so the LLM reads less and costs less; then check nothing important was missed.
      Also: upload / Document Intelligence size limits, time and cost per document, a queue
- **Versioning per applicant:** link each applicant to the rulebook version used to
      **extract** their values and to **evaluate** them; re-check old applicants when rules change
- **Human approval:** separate **Save draft** and **Approve & publish**; before publishing,
      test the rules on the test applicants and show which decisions would change
- Background queue (Event Grid / Storage Queue + Functions)
- **Deploy:** backend on Container Apps with Managed Identity, frontend on Static Web Apps,
      roles for the Managed Identity, App Insights, Entra login for underwriters

---

## Azure services

| Need | Service | Version |
|---|---|---|
| Store uploaded files | Blob Storage | v1 |
| Read documents (OCR, with pages) | Document Intelligence (Layout) | v1 |
| LLM | Azure OpenAI in Foundry, structured outputs (gpt-4.1-mini) | v1 |
| Save the rules (v1), applicants and results (v2) | Azure Database for MySQL – Flexible Server (Entra sign-in, no password) | v1 |
| Search large documents | AI Search (⚠️ Standard ≈ $250/month: create it only for v3, or use Free) | v3 |
| Hosting, monitoring, login | Container Apps, Static Web Apps, App Insights, Entra ID | v3 |

**Cost:** MySQL smallest size ≈ $12–15/month (stop it when not in use); Document Intelligence
≈ $10 per 1,000 pages; gpt-4.1-mini costs cents for a demo.
