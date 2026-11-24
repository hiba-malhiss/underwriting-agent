"""The rulebook format: what a parameter and a rule look like.

The LLM fills a rulebook from the guidelines; a human approves it; code runs it (evaluator.py).
The code only knows these SHAPES, never specific parameters, so a new parameter the LLM adds
(e.g. `hba1c`) works without a code change.

A rule reads: "IF <conditions> THEN <outcome>", e.g.

    {"name": "max_age", "rule_type": "automatic",
     "conditions": {"all_of": [{"parameter": "age", "operator": "greater_than", "value": 65}]},
     "outcome": "decline", ...}

`judgment` rules ("at the underwriter's discretion") have no conditions: they always go to a
human.

Pydantic models, so the same shapes give the API's schemas and the LLM's strict JSON schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Names are stable identifiers the rules point to: lower_snake_case, e.g. "age", "max_age"
NAME_PATTERN = r"^[a-z][a-z0-9_]*$"

ValueType = Literal["number", "boolean", "enum", "list", "text"]

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
]

# automatic: code decides from the conditions; judgment: always goes to a human
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
    quote: str = Field(min_length=1)


class Parameter(Strict):
    """A fact about an applicant that the rules use, e.g. age, BMI, smoker, conditions."""

    name: str = Field(pattern=NAME_PATTERN)
    value_type: ValueType
    description: str
    # enum: the one value it can take; list: the values it can contain
    allowed_values: list[str] | None = None
    unit: str | None = None  # e.g. "years", "kg", "%"
    source: Source


class Condition(Strict):
    """One test on one parameter, e.g. age greater_than 65."""

    parameter: str
    operator: Operator
    value: Scalar | list[str]


class ConditionGroup(Strict):
    """Conditions joined by AND (`all_of`) or OR (`any_of`); groups can be nested."""

    all_of: list[Condition | ConditionGroup] | None = None
    any_of: list[Condition | ConditionGroup] | None = None


class Rule(Strict):
    name: str = Field(pattern=NAME_PATTERN)
    description: str  # the rule in plain words, for the reviewer
    rule_type: RuleType
    conditions: ConditionGroup | None = None  # required for automatic rules, none for judgment
    outcome: Outcome
    source: Source


class Rulebook(Strict):
    """One version's parameters and rules."""

    parameters: list[Parameter]
    rules: list[Rule]
