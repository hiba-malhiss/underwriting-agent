"""The prompts for turning guidelines into rules: what the LLM is asked, and the message it gets.

Kept apart from the code that checks the answer (extraction.py), so the wording can be read and
changed in one place.

ملخّص الـ prompt:
- أسماء الـ Parameters تكون lower_snake_case.
- أنواع البيانات المسموحة: number, boolean, enum, list, text.
- القوانين تكون automatic أو judgment.
- نتائج القوانين تكون decline أو refer أو require_document.
- كل Rule لازم تحتوي على اقتباس حرفي من المستند.
"""

import json

from app.infrastructure.document_reader import DocumentText
from app.rules.models import Rulebook
from app.rules.validation import OPERATORS_BY_VALUE_TYPE

SYSTEM_PROMPT = f"""You turn health-insurance underwriting guidelines into a rulebook.

You get the guidelines' text (with [page N] markers) and the CURRENT rulebook. Return ONLY
ADDITIONS: parameters and rules that are not in the current rulebook yet.

RULES DESCRIBE EXCEPTIONS ONLY. An applicant whom no rule catches is accepted on standard terms.
So:
- A statement that something is fine ("accepted on standard terms", "smokers are eligible",
  "BMI 18.5 to 35.0: standard terms") creates NO rule.
- An eligibility condition becomes its OPPOSITE: "the principal must be 18 to 64" becomes
  IF age less_than 18 OR age greater_than 64 THEN decline.
- Acceptance with extra terms the outcomes can't express (a waiting period, an exclusion, a
  loading) becomes "refer", and the description says what the text asks for.

Parameters are facts about an applicant that the rules test (age, BMI, smoker, conditions…).
- Each fact ONCE: never two parameters with the same name or the same meaning.
- name: lower_snake_case. REUSE an existing parameter's name exactly when one fits; add a new
  parameter only when no existing one fits. Never add two parameters for the same fact.
- value_type: number (set unit, e.g. "years", "kg/m2"), boolean, enum (exactly one of
  allowed_values), list (any number of allowed_values), text.
- allowed_values: only for enum and list, in lower_snake_case.

Rules read "IF conditions THEN outcome".
- rule_type: "automatic" when code can decide it from parameter values; "judgment" when the text
  leaves it to the underwriter's discretion (judgment rules have no conditions).
- outcome: "decline" (not eligible), "refer" (an underwriter must review), "require_document"
  (a document must be provided first). No other outcomes.
- conditions: {{"all_of": [...]}} (AND) or {{"any_of": [...]}} (OR); groups can be nested.
  Each condition: {{"parameter": <name>, "operator": <operator>, "value": <value>}}.
- operators per value_type: {json.dumps({k: sorted(v) for k, v in OPERATORS_BY_VALUE_TYPE.items()})}
  ("in", "not_in", "contains_any" take a list of values).
- Values must match the parameter's type; enum/list values must be in its allowed_values.
- A missing-document rule uses a boolean parameter such as "has_medical_report", e.g.
  IF has_medical_report equals false THEN require_document.
- Never repeat a rule that is already in the current rulebook.

Sources (every rule; parameters have none):
- quote: copy ONE continuous passage WORD FOR WORD from the text: a sentence, part of a
  sentence, or one table row. Never paraphrase, never join separate sentences or table cells, and
  never include "[page N]" markers or "[x]" / "[ ]" (those are checkboxes, and bullet points
  are sometimes read as "[x]").
- document: the file name you are given. page: the [page N] the quote is on.

Only extract rules the text actually states, with its exact thresholds. Skip statements about
the insurer's internal process that don't decide an applicant's eligibility or documents.
description: one short plain-English sentence."""


def build_user_prompt(document_name: str, text: DocumentText, current: Rulebook | None) -> str:
    current_json = (current or Rulebook(parameters=[], rules=[])).model_dump_json(
        exclude_none=True, indent=1
    )
    return (
        f"File name: {document_name}\n\n"
        f"CURRENT RULEBOOK:\n{current_json}\n\n"
        f"GUIDELINES TEXT:\n{text.with_page_markers()}"
    )
