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
  `{ "parameter": "age", "operator": "greater_than", "value": 65 }`. The code knows the *shape* of
  rules, not their names, so new parameters work without code changes.
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
- The code that runs rules: for each rule the applicant **passed**, **not passed** (the rule's
  outcome happens), **missing data**, or **needs judgment**, with an explanation (+ tests)
- MySQL connection and tables (created by the app at start; migrations come in v2)
- **Parameters come from the guidelines, nothing is built in** (like AUI's parameters.aui.json):
  the current rulebook is the registry. The LLM reuses its names and adds new ones when needed;
  rules may only use declared parameters. Each parameter has a **kind**: `application` (the form),
  `medical` (reports and declarations) or `document` (which files were provided, filled by code
  from the uploads' types). Checks: allowed values are snake_case codes; a list can gain values
  (flagged)
- **Operators** include `between` ([low, high]) and `is_missing` / `is_present`
- Rules from guidelines, in 4 parts:
  - **A. Read the guidelines:** Document Intelligence (Layout) turns the PDF into **one continuous
    text** in reading order, plus where each page starts and ends in it. A paragraph split across
    two pages stays whole, and every quote can still be traced to its page (or pages)
  - **B. LLM suggests additions, in 2 steps** (like AUI: parameters first, then the rules that
    use them). Both steps get the text (with `[page N]` markers) and a **snapshot** of the
    current rulebook: a short list written by code (each parameter with its kind, type and
    values; each rule as one line "IF … THEN …"), not the full JSON. Only **additions** come back
    - **Step 1, what the guidelines require:** every statement that decides something, with its
      exact quote and a one-sentence summary, marked `add_rule`, `already_covered` (a current
      rule does it) or `no_rule` (it only says something is fine)
    - **Step 2, the rules:** the numbered `add_rule` requirements → the parameters (written
      first, reusing the snapshot's names: `age`, not `applicant_age`) and the rules; each rule
      says which requirement it encodes, and code gives it that requirement's checked quote as
      its source (so step 2 can't invent a quote). Parameters sit in step 2, not step 1, so a
      rule that needs a new parameter can still add it during a repair
    - **Code checks after each step:** each quote is really in the text (ignoring line breaks and
      spaces, so quotes across pages still match) and its page; the rulebook checks; a duplicate
      of a current rule is skipped; and **coverage: every `add_rule` requirement has a rule** (so
      a missed rule shows up as a problem, and the page lists any still missed)
    - **Repair loop:** if a step has problems, they go back to the LLM with its own answer, to
      fix (at most 2 times); the answer with the fewest problems is kept. A plain loop, no
      LangGraph (the flow is a straight line)
  - **C. API:** `POST /rules/proposals` (a guideline file → suggested additions; not stored) and
    `POST /rules/versions` (the approved additions → version N+1 = **all the current rules + the
    approved additions**; nothing is removed or changed)
  - **D. Rules page:** each suggested rule next to its quote and page, **approve / reject**, then
    **Save**; and the current version's parameters and rules
  - **E. Answer key:** the rules a sample guideline should give, written by hand, and a script
    that compares a proposal with it: found, missed, extra. It measures whether a change (prompt,
    steps, model) made extraction better

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
| `parameters` | `id`, `rulebook_version_id`, `name`, `value_type`, `allowed_values` (JSON), `unit`, `description`, `source` (JSON) |
| `rules` | `id`, `rulebook_version_id`, `name`, `description`, `rule_type` (automatic / judgment), `conditions` (JSON), `outcome` (decline / refer / require_document), `source` (JSON) |

---

## Version 2: nicer and safer

- **Computed parameters** (like AUI's computations): a parameter of kind `computed` with a
  **formula** in the rulebook, e.g. `round({weight_kg} / ({height_cm} / 100) ** 2, 1)` for BMI or
  `years_since({date_of_birth})` for age, run by a small safe evaluator (no `eval`). Checks: the
  formula parses, uses declared parameters, and has no cycles. Until then, age and BMI are read
  from the documents as numbers
- **Save applicants:** create an applicant (name), list them, open one; their documents in Blob
  Storage; add documents later and merge with the values already extracted
- Tables: `applicants` (`id`, `full_name`, `created_at`), `extracted_values` (`applicant_id`,
  `parameter_code`, `value`, `sources`, `conflict`), `evaluations` (`applicant_id`,
  `rulebook_version_id`, `created_at`), `rule_results`, `decisions`
- Underwriter records the decision (accept / decline / refer) with a note
- Migrations with Alembic
- Table rules (e.g. BMI limit by age band)
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
- Test applicants (expected outcome for each)

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
