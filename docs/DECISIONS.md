# What testing on real guidelines taught us

Each row is a problem we saw when the LLM read a real guideline PDF
(`health-underwriting-guidelines.pdf`), and the change it led to. The pattern behind most of them:
**the prompt guides, the code checks, the human approves.** A fix in code (a check, or a shape that
makes the mistake impossible) is preferred over a longer prompt.

## Changes made

| # | What we saw | Why it happened | What we changed | Commit |
|---|---|---|---|---|
| 1 | Every rule had invented conditions such as "age less_than 0" | A condition group had two lists (`all_of`, `any_of`); strict JSON makes every field required, so the LLM filled the unused one | One list plus how to join it: `{"match": "all" \| "any", "items": [...]}` | `a394f65` |
| 2 | A broken condition silently became an empty group | Pydantic ignored unknown fields | `extra="forbid"` on every model: unknown fields are refused | `bcbd140` |
| 3 | Quotes "not found" in the text | Document Intelligence writes checkboxes as `:selected:`, and reads bullet points as ticked boxes | Checkboxes shown as `[x]` / `[ ]`, ignored when matching quotes | `1c0966d` |
| 4 | Quotes "not found" across two bullet points | A stray `.` or `•` between bullets in the text | Bullet symbols standing alone are ignored when matching quotes | `17d8863` |
| 5 | The same rule suggested twice under new names | Duplicates were found by rule name, and the LLM renames rules each run | Duplicates found by what a rule does: type, outcome and conditions | `270138b` |
| 6 | Allowed values like `"Essential"`, and parameters no rule used | Nothing checked them | Allowed values must be lower_snake_case; a new parameter no rule uses is flagged | `85293c2`, `270138b` |
| 7 | Problems were found, but only shown to the reviewer | Nothing sent them back to the LLM | **Repair loop:** problems go back with the LLM's own answer, at most 2 times; the answer with the fewest problems is kept | `51939ba` |
| 8 | Whole rules missing (65 or over, marriage and birth certificates, an unlisted condition) | One call had to find everything and write the rules at once; nothing could notice a missing rule | **2 steps:** first the requirements (with quotes), then the rules for them; **coverage check:** a requirement with no rule is a problem | `542ba48` |
| 9 | "Missing the report AND the ECG" instead of OR (age 60–64) | A logic slip by the LLM | A prompt example of a missing-document rule with OR (in the last run the LLM wrote one rule per document, which is also correct) | `542ba48` |
| 10 | The prompt would grow with every saved rule | The full rulebook JSON was sent | A **snapshot**: one line per parameter and rule, written by code | `8290f18` |
| 11 | "Accept, standard terms" lines became "refer" rules (normal BMI, controlled hypertension, mild asthma) | The LLM decided which lines need a rule, and the coverage check then forced a rule for each | Step 1 only copies the **outcome the text states**; **code decides** what needs a rule; each rule's outcome must match its requirement's | `90ad996` |
| 12 | Judgment rules (waiting periods, pending information) applied to every applicant | Judgment rules had no conditions, so they always went to an underwriter | **Every rule has conditions**; a judgment rule's conditions say who it's about, and only those applicants go to an underwriter | `bd0f101` |
| 13 | Whole sections missing (ages 18–64, residency), and nothing reported them as missed | Likely (not yet logged): the repair prompt said "quote not found → remove the item", and the loop kept the answer with the fewest problems, so deleting a hard-to-quote requirement looked like a fix | **A repair never deletes:** an answer with fewer items is never kept, and the model is told to send them back; what it can't fix stays, flagged, for the underwriter to decide | `ea763f4` |

## Still open

| What we saw | Planned change |
|---|---|
| Every medical rule quotes the whole medical table | Read tables as Markdown (one row per line), so each rule quotes its own row |
| A child over 25 in full-time education passes | Better rule logic; caught by an answer key / test applicants |
| The newborn exception contradicts the residency rule | Same |
| Smokers, type 2 diabetes ≤ 7.5 and pregnancy are "refer" | An "accept with terms" outcome |
| No way to tell if a change made extraction better or worse | An **answer key**: the rules the PDF should give, and a score (found / missed / extra) |
