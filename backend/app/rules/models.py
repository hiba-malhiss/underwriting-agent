"""The rulebook format: what a parameter and a rule look like.

The LLM fills a rulebook from the guidelines; a human approves it; code runs it (evaluator.py).
The code only knows these SHAPES, never specific parameters, so a new parameter the LLM adds
(e.g. `hba1c`) works without a code change.

A rule reads: "IF <conditions> THEN <outcome>", e.g.

    {"name": "max_age", "rule_type": "automatic",
     "conditions": {"match": "all",
                    "items": [{"parameter": "age", "operator": "greater_than", "value": 65}]},
     "outcome": "decline", ...}

Every rule has conditions, saying WHEN it applies. For a `judgment` rule ("heart conditions are
at the underwriter's discretion") they say who it's about, and an underwriter decides for them.

Pydantic models, so the same shapes give the API's schemas and the LLM's strict JSON schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Names are stable identifiers the rules point to: lower_snake_case, e.g. "age", "max_age"
NAME_PATTERN = r"^[a-z][a-z0-9_]*$"

ValueType = Literal["number", "boolean", "enum", "list", "text", "date"]

# Where a parameter's value comes from:
# application: the application form · medical: medical reports and declarations ·
# document: which files were provided (filled by code from the uploads' document types)
ParameterKind = Literal["application", "medical", "document"]

# Operators are words, not symbols (">="): clearer for reviewers, harder for the LLM to garble
Operator = Literal[
    "greater_than",
    "greater_or_equal",
    "less_than",
    "less_or_equal",
    "equals",
    "not_equals",
    "in",  # the value is one of a list
    "not_in",
    "contains",  # a list parameter contains a value
    "not_contains",
    "contains_any",  # a list parameter contains at least one of the values
    "between",  # a number within [low, high], both included
    "is_missing",  # no value was found (takes no value)
    "is_present",  # a value was found (takes no value)
]

# When the conditions are true: automatic → the outcome happens; judgment → an underwriter decides
RuleType = Literal["automatic", "judgment"]
# decline: not covered; refer: an underwriter decides; require_document: wait for a document.
# No rule applies → accepted as normal (rules only describe the exceptions).
Outcome = Literal["decline", "refer", "require_document"]
Scalar = int | float | bool | str


class Strict(BaseModel):
    """Unknown fields are refused, not ignored. Otherwise a broken condition (e.g. a misspelled
    field) would silently turn into an empty group, and the mistake would be lost."""

    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    """Where something came from: the exact quote, so a human can check it in seconds."""

    document: str
    page: int | None = None
    last_page: int | None = None  # set when the quote runs onto the next page
    quote: str = Field(min_length=1)


class Parameter(Strict):
    """A fact about an applicant that the rules use, e.g. age, BMI, smoker, conditions.

    Every parameter comes from the guidelines (through the LLM, approved by a human); the code
    knows no parameter by name. The current rulebook is the registry: rules may only use the
    parameters it declares.

    No source quote: the same fact appears in many sentences, and every RULE that uses it has
    its own quote saying why it matters."""

    name: str = Field(pattern=NAME_PATTERN)
    kind: ParameterKind
    value_type: ValueType
    description: str
    # enum: the one value it can take; list: the values it can contain
    allowed_values: list[str] | None = None
    unit: str | None = None  # e.g. "years", "kg", "%"


class Condition(Strict):
    """One test on one parameter, e.g. age greater_than 65."""

    parameter: str
    operator: Operator
    # None only for is_missing / is_present; a list for in, not_in, contains_any, between
    value: Scalar | list[Scalar] | None = None


class ConditionGroup(Strict):
    """Conditions joined by AND (match "all") or OR (match "any"); an item can be another group.

    One list plus how to join it, not two lists (all_of / any_of): in strict JSON every field is
    required, so with two lists the LLM filled the unused one with invented conditions."""

    match: Literal["all", "any"]
    items: list[Condition | ConditionGroup]


class RuleLogic(Strict):
    """What a rule does, without its source. The LLM writes this in the rules step; code adds the
    source from the requirement the rule encodes (requirements.py)."""

    name: str = Field(pattern=NAME_PATTERN)
    description: str  # the rule in plain words, for the reviewer
    rule_type: RuleType
    # Required (validation reports a rule without them). Optional here only so an old saved rule
    # without conditions can still be loaded and reported, instead of breaking the page
    conditions: ConditionGroup | None = None
    outcome: Outcome


class Rule(RuleLogic):
    source: Source


class Rulebook(Strict):
    """One version's parameters and rules."""

    parameters: list[Parameter]
    rules: list[Rule]
