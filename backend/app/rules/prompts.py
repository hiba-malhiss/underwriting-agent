"""The prompts for turning guidelines into rules: what the LLM is asked, and the message it gets.

Kept apart from the code that checks the answer (extraction.py), so the wording can be read and
changed in one place.

ملخّص الـ prompt:
- أسماء الـ Parameters تكون lower_snake_case.
- أنواع البيانات المسموحة: number, boolean, enum, list, text.
- القوانين تكون automatic أو judgment.
- نتائج القوانين تكون decline أو refer أو require_document.
- كل Rule لازم تحتوي على اقتباس حرفي من المستند.
- إذا فشلت الإجابة بالفحص، build_repair_prompt بيرجّع المشاكل للـ LLM ليصلّحها.
"""

import json

from app.infrastructure.document_reader import DocumentText
from app.rules.models import Rulebook
from app.rules.validation import OPERATORS_BY_VALUE_TYPE

SYSTEM_PROMPT = f"""You turn health-insurance underwriting guidelines into a rulebook.

You get the guidelines' text (with [page N] markers) and the CURRENT rulebook. Return ONLY
ADDITIONS: rules that are not in the current rulebook yet, and the parameters they use.

RULES DESCRIBE EXCEPTIONS ONLY. An applicant whom no rule catches is accepted on standard terms.
So:
- A statement that something is fine ("accepted on standard terms", "smokers are eligible",
  "BMI 18.5 to 35.0: standard terms") creates NO rule.
- An eligibility condition becomes its OPPOSITE: "the principal must be 18 to 64" becomes
  IF age less_than 18 OR age greater_than 64 THEN decline.
- Acceptance with extra terms the outcomes can't express (a waiting period, an exclusion, a
  loading) becomes "refer", and the description says what the text asks for.

Parameters are facts about an applicant that the rules test (age, BMI, smoker, conditions…).
The CURRENT rulebook's parameters are the registry:
- REUSE a current parameter's name exactly whenever it fits; never add a second parameter for the
  same fact. You may add allowed_values to a current enum or list (e.g. new plan names).
- A new parameter needs: name (lower_snake_case), kind, value_type, description, allowed_values
  (enum and list only), unit (numbers).
- kind: "application" (from the application form: plan applied for, relationship, residency…),
  "medical" (from medical reports and declarations: height, weight, conditions, HbA1c…),
  "document" (which documents the applicant provided: a list of document types, e.g.
  documents_provided with allowed_values ["medical_report", "ecg", …]).
- value_type: number, boolean, enum (exactly one of allowed_values), list (any number of
  allowed_values), text, date (e.g. date_of_birth).
- Age and BMI are read as numbers (kind "application" for age, "medical" for bmi), not
  calculated.

Rules read "IF conditions THEN outcome".
- rule_type: "automatic" when code can decide it from parameter values; "judgment" when the text
  leaves it to the underwriter's discretion (judgment rules have no conditions).
- outcome: "decline" (not eligible), "refer" (an underwriter must review), "require_document"
  (a document must be provided first). No other outcomes.
- conditions: {{"match": "all", "items": [...]}} (AND) or {{"match": "any", "items": [...]}}
  (OR). An item is a condition or another group, e.g. A AND (B OR C) is
  {{"match": "all", "items": [A, {{"match": "any", "items": [B, C]}}]}}.
  Each condition: {{"parameter": <name>, "operator": <operator>, "value": <value>}}.
- operators per value_type: {json.dumps({k: sorted(v) for k, v in OPERATORS_BY_VALUE_TYPE.items()})}
  ("in", "not_in", "contains_any" take a list of values; "between" takes [low, high], both
  included; "is_missing" and "is_present" take no value: use null).
- Values must match the parameter's type; enum/list values must be in its allowed_values.
- A missing-document rule tests the "document" parameter, e.g.
  IF age between [50, 59] AND documents_provided not_contains "medical_report"
  THEN require_document.
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


def build_repair_prompt(problems: list[str]) -> str:
    """The message after an answer that failed the checks: the problems, and how to fix them."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return f"""Your answer failed these checks:
{listed}

Send the WHOLE answer again with every problem fixed:
- Keep every rule and parameter that had no problem exactly as it was. Don't add new rules.
- "quote not found": copy ONE continuous passage word for word from the guidelines text. If the
  text has no such passage, remove the rule.
- "unknown parameter": use a parameter that exists, or add it to parameters.
- "not used by any rule": remove the parameter.
- A name already used by something different: pick another name, or reuse the existing one if
  it's the same fact.
- Values and allowed_values must follow the format above (lower_snake_case values, the operators
  allowed for the type, values in the parameter's allowed_values)."""
