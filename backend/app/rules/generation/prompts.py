"""The prompts for turning guidelines into rules: what the LLM is asked, and the messages it gets.

Kept apart from the code that checks the answers (requirements.py, extraction.py), so the
wording can be read and changed in one place.

ملخّص الـ prompt:
- خطوتين: أولاً REQUIREMENTS_PROMPT بيطلع كل متطلب من المستند مع اقتباس حرفي والنتيجة
  المكتوبة بالنص (accept, refer, decline…)، والكود بيقرر إذا بدّه rule،
  وبعدين RULES_PROMPT بيكتب الـ parameters والـ rules لكل متطلب.
- كل Rule بتقول أي متطلب بتغطي، والكود بياخد الاقتباس من المتطلب.
- أسماء الـ Parameters تكون lower_snake_case.
- أنواع البيانات المسموحة: number, boolean, enum, list, text, date.
- القوانين تكون automatic أو judgment.
- نتائج القوانين تكون decline أو refer أو require_document.
- إذا فشلت الإجابة بالفحص، build_repair_prompt بيرجّع المشاكل للـ LLM ليصلّحها.
"""

import json

from app.infrastructure.document_reader import DocumentText
from app.rules.domain.models import Rulebook
from app.rules.domain.validation import OPERATORS_BY_VALUE_TYPE
from app.rules.generation.requirements import FoundRequirement
from app.rules.generation.snapshot import snapshot

_SNAPSHOT_FORMAT = """a snapshot of the CURRENT rulebook (one line per parameter:
name (kind, type: allowed values, unit): description; one line per rule:
IF conditions THEN outcome)"""

_EXCEPTIONS_ONLY = """RULES DESCRIBE EXCEPTIONS ONLY. An applicant whom no rule catches is
accepted on standard terms. A statement that something is fine ("accepted on standard terms",
"smokers are eligible", "BMI 18.5 to 35.0: standard terms") needs NO rule."""

# ---- Step 1: requirements ----

REQUIREMENTS_PROMPT = f"""You read health-insurance underwriting guidelines and list what they
require of an applicant. Rules are written later, from your list.

You get the guidelines' text (with [page N] markers) and {_SNAPSHOT_FORMAT}.

List EVERY statement that decides something about an applicant: who is eligible or not, which
documents they must provide, which medical findings are accepted, accepted with terms, referred
or declined. Go through the text section by section, and every row of a table that decides
something, INCLUDING the ones that are simply accepted. Keep a condition and its exceptions
together ("children up to 21, or 25 if in full-time education" is ONE requirement), but one
outcome per requirement: "BMI above 40: not eligible for Enhanced; Essential and Family are
referred" is TWO requirements (decline, refer). Skip the insurer's internal process (who signs,
how long a review takes, waiting periods of the policy) unless it decides an applicant's
eligibility or documents.

You don't write rules here: you only copy what the text says.

For each requirement:
- quote: copy ONE continuous passage WORD FOR WORD from the text: a sentence, part of a
  sentence, or one table row. Never paraphrase, never join separate sentences or table cells, and
  never include "[page N]" markers or "[x]" / "[ ]" (those are checkboxes, and bullet points
  are sometimes read as "[x]").
- summary: one sentence that states the requirement in full, with its numbers, plan names and
  documents, so it can be understood without the text.
- outcome: what the TEXT says happens to the applicant, nothing else:
  "accept": eligible on standard terms ("Accept, standard terms", "smokers are eligible");
  "accept_with_terms": eligible with a waiting period, an exclusion or a premium loading;
  "refer": an underwriter reviews or decides ("refer to medical underwriter", "at the
  underwriter's discretion");
  "decline": not eligible ("not eligible", "must be 18 to 64" for those outside it);
  "require_document": a document must be provided.
- covered_by: the name of the current rule (from the snapshot) that already does exactly this,
  or null."""


def build_requirements_prompt(
    document_name: str, text: DocumentText, current: Rulebook | None
) -> str:
    return (
        f"File name: {document_name}\n\n"
        f"CURRENT RULEBOOK (snapshot):\n{snapshot(current)}\n\n"
        f"GUIDELINES TEXT:\n{text.with_page_markers()}"
    )


# ---- Step 2: rules ----

RULES_PROMPT = f"""You turn numbered requirements from health-insurance underwriting guidelines
into rules.

You get the REQUIREMENTS (number, page, summary and the guidelines' exact words) and
{_SNAPSHOT_FORMAT}. Write the parameters and rules the requirements need: EVERY requirement gets
at least one rule, and each rule's "requirement" is the number of the requirement it encodes.
A rule's outcome is its requirement's outcome, except "accept_with_terms", which becomes "refer"
(the rules have no outcome for terms yet; the description says what the terms are).
Write only what the requirement states, with its exact thresholds. Never repeat a rule that is
already in the current rulebook.

{_EXCEPTIONS_ONLY}
- An eligibility condition becomes its OPPOSITE: "the principal must be 18 to 64" becomes
  IF age less_than 18 OR age greater_than 64 THEN decline.

Parameters are facts about an applicant that the rules test (age, BMI, smoker, conditions…).
Write them first. The CURRENT rulebook's parameters are the registry:
- REUSE a current parameter's name exactly whenever it fits; never add a second parameter for the
  same fact. You may add allowed_values to a current enum or list (e.g. new plan names): send
  that parameter again in full, with its current and new values.
- A new parameter needs: name (lower_snake_case), kind, value_type, description, allowed_values
  (enum and list only, lower_snake_case codes like "type_2_diabetes"), unit (numbers).
- kind: "application" (from the application form: plan applied for, relationship, residency…),
  "medical" (from medical reports and declarations: height, weight, conditions, HbA1c…),
  "document" (which documents the applicant provided: a list of document types, e.g.
  documents_provided with allowed_values ["medical_report", "ecg", …]).
- value_type: number, boolean, enum (exactly one of allowed_values), list (any number of
  allowed_values), text, date (e.g. date_of_birth).
- Age and BMI are read as numbers (kind "application" for age, "medical" for bmi), not
  calculated.

Rules read "IF conditions THEN outcome".
- EVERY rule has conditions: they say WHEN it applies. A rule without conditions would apply to
  every applicant.
- rule_type: "automatic" when the outcome follows directly from the values; "judgment" when the
  text leaves the decision to the underwriter's discretion. A judgment rule's conditions say who
  it's about ("heart conditions are at the underwriter's discretion": IF conditions contains
  "heart_disease"), and an underwriter decides for them.
- When the text gives no clear test ("complex medical histories are assessed individually"),
  use one yes/no parameter that names the fact (complex_medical_history), with a clear
  description. Never invent thresholds the text doesn't give.
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
- A missing-document rule tests the "document" parameter. When ANY of several documents is
  missing, use "any": IF age between [60, 64] AND (documents_provided not_contains
  "medical_report" OR documents_provided not_contains "ecg") THEN require_document.
description: one short plain-English sentence."""


def build_rules_prompt(requirements: list[FoundRequirement], current: Rulebook | None) -> str:
    listed = "\n".join(
        f"{r.number}. (page {r.source.page or '?'}, outcome: {r.outcome}) {r.summary}\n"
        f'   Text: "{r.source.quote}"'
        for r in requirements
    )
    return f"CURRENT RULEBOOK (snapshot):\n{snapshot(current)}\n\nREQUIREMENTS:\n{listed}"


# ---- Both steps: fixing an answer ----


def build_repair_prompt(problems: list[str]) -> str:
    """The message after an answer that failed the checks: the problems, and how to fix them."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return f"""Your answer failed these checks:
{listed}

Send the WHOLE answer again with every problem fixed. Keep everything that had no problem
exactly as it was.
- "quote not found": copy ONE continuous passage word for word from the guidelines text. If the
  text has no such passage, remove that item.
- "no rule written for it": add the rule(s) for that requirement.
- "there is no requirement N": set the rule's requirement to the right number.
- "its outcome is …, but requirement N says …": use the outcome given, or point the rule to the
  right requirement.
- "there is no current rule": use a name from the snapshot, or null.
- "unknown parameter": use a parameter that exists, or add it to parameters.
- "not used by any rule": remove the parameter.
- A name already used by something different: pick another name, or reuse the existing one if
  it's the same fact.
- Values and allowed_values must follow the format above (lower_snake_case values, the operators
  allowed for the type, values in the parameter's allowed_values)."""
