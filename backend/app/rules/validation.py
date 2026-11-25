"""Checks a rulebook before anyone can approve it.

The LLM can produce rules that look right but can't run: a parameter that doesn't exist,
"greater_than" on a yes/no value, "65" as text for a number. These checks find all of them at
once and say which rule and what to fix, so the review page can show them next to the rule.

The shape itself (fields, types, name format) is already checked by pydantic in models.py; this
file checks what pydantic can't: how the parts fit together.
"""

from dataclasses import dataclass

from app.core.errors import BadRequestError
from app.rules.models import Condition, ConditionGroup, Parameter, Rule, Rulebook, ValueType

# Which operators make sense for each value type
OPERATORS_BY_VALUE_TYPE: dict[ValueType, set[str]] = {
    "number": {
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "equals",
        "not_equals",
    },
    "boolean": {"equals", "not_equals"},
    "enum": {"equals", "not_equals", "in", "not_in"},
    "list": {"contains", "not_contains", "contains_any"},
    "text": {"equals", "not_equals"},
}

# Operators that compare against a list, e.g. {"operator": "in", "value": ["a", "b"]}
LIST_VALUE_OPERATORS = {"in", "not_in", "contains_any"}


@dataclass(frozen=True)
class Problem:
    where: str  # "parameter bmi" or "rule max_age"
    message: str


class RulebookInvalidError(BadRequestError):
    """The rulebook has problems and can't be saved. Answered with 400 and the list."""

    def __init__(self, problems: list[Problem]):
        self.problems = problems
        super().__init__("; ".join(f"{p.where}: {p.message}" for p in problems))


def find_problems(rulebook: Rulebook) -> list[Problem]:
    """Every problem in the rulebook; an empty list means it can run."""
    problems: list[Problem] = []
    parameters: dict[str, Parameter] = {}

    for parameter in rulebook.parameters:
        where = f"parameter {parameter.name}"
        if parameter.name in parameters:
            problems.append(Problem(where, "is defined twice"))
        parameters[parameter.name] = parameter
        needs_values = parameter.value_type in ("enum", "list")
        if needs_values and not parameter.allowed_values:
            problems.append(
                Problem(where, f"{parameter.value_type} parameters need allowed_values")
            )
        if not needs_values and parameter.allowed_values:
            problems.append(
                Problem(where, f"{parameter.value_type} parameters can't have allowed_values")
            )

    rule_names: set[str] = set()
    for rule in rulebook.rules:
        where = f"rule {rule.name}"
        if rule.name in rule_names:
            problems.append(Problem(where, "is defined twice"))
        rule_names.add(rule.name)
        problems += [Problem(where, message) for message in _rule_problems(rule, parameters)]

    return problems


def ensure_valid(rulebook: Rulebook) -> None:
    problems = find_problems(rulebook)
    if problems:
        raise RulebookInvalidError(problems)


def _rule_problems(rule: Rule, parameters: dict[str, Parameter]) -> list[str]:
    problems = []
    if rule.rule_type == "automatic" and rule.conditions is None:
        problems.append("an automatic rule needs conditions")
    if rule.rule_type == "judgment" and rule.conditions is not None:
        problems.append("a judgment rule has no conditions: it always goes to a human")
    if rule.conditions is not None:
        problems += _group_problems(rule.conditions, parameters)
    return problems


def _group_problems(group: ConditionGroup, parameters: dict[str, Parameter]) -> list[str]:
    if not group.items:
        return ["a condition group can't be empty"]
    problems = []
    for item in group.items:
        if isinstance(item, ConditionGroup):
            problems += _group_problems(item, parameters)
        else:
            problems += _condition_problems(item, parameters)
    return problems


def _condition_problems(condition: Condition, parameters: dict[str, Parameter]) -> list[str]:
    parameter = parameters.get(condition.parameter)
    if parameter is None:
        return [f"unknown parameter '{condition.parameter}'"]
    allowed_operators = OPERATORS_BY_VALUE_TYPE[parameter.value_type]
    if condition.operator not in allowed_operators:
        return [
            f"'{condition.operator}' can't be used on {parameter.value_type} "
            f"'{parameter.name}' (use: {', '.join(sorted(allowed_operators))})"
        ]

    label = f"'{parameter.name} {condition.operator}'"
    if condition.operator in LIST_VALUE_OPERATORS:
        if not isinstance(condition.value, list) or not condition.value:
            return [f"{label} needs a list of values"]
        values = condition.value
    else:
        if isinstance(condition.value, list):
            return [f"{label} needs a single value, not a list"]
        values = [condition.value]

    if parameter.value_type == "number":
        # bool is an int in Python: refuse True/False for numbers explicitly
        if not all(isinstance(v, int | float) and not isinstance(v, bool) for v in values):
            return [f"{label} needs a number"]
    elif parameter.value_type == "boolean":
        if not all(isinstance(v, bool) for v in values):
            return [f"{label} needs true or false"]
    elif not all(isinstance(v, str) for v in values):
        return [f"{label} needs text"]
    elif parameter.allowed_values is not None:
        not_allowed = [v for v in values if v not in parameter.allowed_values]
        if not_allowed:
            return [f"{label}: {', '.join(not_allowed)} not in the allowed values"]
    return []
