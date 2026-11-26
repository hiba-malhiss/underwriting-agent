"""Checks a rulebook before anyone can approve it.

The LLM can produce rules that look right but can't run: a parameter that doesn't exist,
"greater_than" on a yes/no value, "65" as text for a number. These checks find all of them at
once and say which rule and what to fix, so the review page can show them next to the rule.

The shape itself (fields, types, name format) is already checked by pydantic in models.py; this
file checks what pydantic can't: how the parts fit together.
"""

import re
from dataclasses import dataclass

from app.core.errors import BadRequestError
from app.rules.domain.models import Condition, ConditionGroup, Parameter, Rule, Rulebook, ValueType

# Allowed values are codes, like names: "type_2_diabetes", not "Type 2 diabetes"
VALUE_NAME = re.compile(r"^[a-z0-9][a-z0-9_]*$")

# Operators every type supports: they test whether a value was found at all
PRESENCE_OPERATORS = {"is_missing", "is_present"}

# Which operators make sense for each value type
OPERATORS_BY_VALUE_TYPE: dict[ValueType, set[str]] = {
    "number": {
        "greater_than",
        "greater_or_equal",
        "less_than",
        "less_or_equal",
        "equals",
        "not_equals",
        "between",
    }
    | PRESENCE_OPERATORS,
    "boolean": {"equals", "not_equals"} | PRESENCE_OPERATORS,
    "enum": {"equals", "not_equals", "in", "not_in"} | PRESENCE_OPERATORS,
    "list": {"contains", "not_contains", "contains_any"} | PRESENCE_OPERATORS,
    "text": {"equals", "not_equals"} | PRESENCE_OPERATORS,
    "date": set(PRESENCE_OPERATORS),  # rules compare a number like age, not the date itself
}

# Operators that compare against a list, e.g. {"operator": "in", "value": ["a", "b"]}
LIST_VALUE_OPERATORS = {"in", "not_in", "contains_any", "between"}


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
        badly_named = [v for v in parameter.allowed_values or [] if not VALUE_NAME.match(v)]
        if badly_named:
            problems.append(
                Problem(where, f"allowed values must be lower_snake_case: {', '.join(badly_named)}")
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
    # Every rule says WHEN it applies, a judgment rule too: without conditions it would apply
    # to every applicant
    if rule.conditions is None:
        problems.append("every rule needs conditions (when it applies)")
    else:
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
    shape_problem = _value_shape_problem(condition, label)
    if shape_problem:
        return [shape_problem]
    if condition.operator in PRESENCE_OPERATORS:
        return []
    values = condition.value if isinstance(condition.value, list) else [condition.value]
    type_problem = _value_type_problem(parameter, values, label)
    return [type_problem] if type_problem else []


def _value_shape_problem(condition: Condition, label: str) -> str | None:
    """No value, one value, or a list, depending on the operator."""
    operator, value = condition.operator, condition.value
    if operator in PRESENCE_OPERATORS:
        return None if value is None else f"{label} takes no value"
    if value is None:
        return f"{label} needs a value"
    if operator == "between":
        is_pair = isinstance(value, list) and len(value) == 2
        if not is_pair:
            return f"{label} needs [low, high]"
        low, high = value
        if _is_number(low) and _is_number(high) and low > high:
            return f"{label}: low is bigger than high"
        return None
    if operator in LIST_VALUE_OPERATORS:
        return None if isinstance(value, list) and value else f"{label} needs a list of values"
    return f"{label} needs a single value, not a list" if isinstance(value, list) else None


def _value_type_problem(parameter: Parameter, values: list, label: str) -> str | None:
    """Every value has the parameter's type (and is allowed, for enum and list)."""
    if parameter.value_type == "number":
        return None if all(_is_number(v) for v in values) else f"{label} needs a number"
    if parameter.value_type == "boolean":
        return None if all(isinstance(v, bool) for v in values) else f"{label} needs true or false"
    if not all(isinstance(v, str) for v in values):
        return f"{label} needs text"
    if parameter.allowed_values is not None:
        not_allowed = [v for v in values if v not in parameter.allowed_values]
        if not_allowed:
            return f"{label}: {', '.join(not_allowed)} not in the allowed values"
    return None


def _is_number(value) -> bool:
    # bool is an int in Python: refuse True/False for numbers explicitly
    return isinstance(value, int | float) and not isinstance(value, bool)
