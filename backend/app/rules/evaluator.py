"""Runs an approved rulebook on one applicant's values. Plain code: no LLM, same input → same
result, and every result explains why.

Each rule is a check the applicant passes or not. Its status is one of:
- passed:         the rule's conditions are false, so nothing happens
- not_passed:     an automatic rule's conditions are true, so its outcome happens (e.g. decline)
- missing_data:   a value it needs wasn't found; never treated as passed
- needs_judgment: a judgment rule's conditions are true, so an underwriter decides

The conditions are checked first for EVERY rule, so a judgment rule only reaches an underwriter
for the applicants it's about (e.g. those with heart disease), not for everyone.

Missing values use three-valued logic (true / false / unknown):
- match "all" (AND): any false → false; else any unknown → unknown; else true
- match "any" (OR):  any true → true; else any unknown → unknown; else false
So a missing value only matters when it could change the answer.

Run only rulebooks that passed validation.find_problems: this module trusts the shapes.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from app.rules.models import Condition, ConditionGroup, Outcome, Rule, Rulebook

Status = Literal["passed", "not_passed", "missing_data", "needs_judgment"]
UNKNOWN = None  # the third truth value, next to True and False

# How each operator reads in an explanation, e.g. "age is 70 (more than 65)"
OPERATOR_WORDS = {
    "greater_than": "more than",
    "greater_or_equal": "at least",
    "less_than": "less than",
    "less_or_equal": "at most",
    "equals": "equal to",
    "not_equals": "different from",
    "in": "one of",
    "not_in": "none of",
    "contains": "includes",
    "not_contains": "excludes",
    "contains_any": "includes any of",
    "between": "between",
}


@dataclass(frozen=True)
class RuleResult:
    rule_name: str
    status: Status
    outcome: Outcome
    explanation: str  # in plain words, e.g. "age is 70 (more than 65)"
    missing_parameters: list[str] = field(default_factory=list)  # needed but not given


def evaluate(rulebook: Rulebook, values: dict[str, Any]) -> list[RuleResult]:
    """`values`: parameter name → the applicant's value. A missing name (or None) is unknown."""
    return [_evaluate_rule(rule, values) for rule in rulebook.rules]


def _evaluate_rule(rule: Rule, values: dict[str, Any]) -> RuleResult:
    notes: list[str] = []
    missing: list[str] = []
    truth = _group(rule.conditions, values, notes, missing)
    explanation = "; ".join(notes)
    if truth is True and rule.rule_type == "judgment":
        return RuleResult(
            rule.name, "needs_judgment", rule.outcome, f"Underwriter review: {explanation}"
        )
    if truth is True:
        return RuleResult(rule.name, "not_passed", rule.outcome, explanation)
    if truth is False:
        return RuleResult(rule.name, "passed", rule.outcome, explanation)
    missing = sorted(set(missing))
    return RuleResult(
        rule.name, "missing_data", rule.outcome, f"Missing: {', '.join(missing)}", missing
    )


def _group(group: ConditionGroup, values: dict[str, Any], notes: list[str], missing: list[str]):
    results = [
        _group(item, values, notes, missing)
        if isinstance(item, ConditionGroup)
        else _condition(item, values, notes, missing)
        for item in group.items
    ]
    if group.match == "all":
        if False in results:
            return False
        return UNKNOWN if UNKNOWN in results else True
    if True in results:
        return True
    return UNKNOWN if UNKNOWN in results else False


def _condition(condition: Condition, values: dict[str, Any], notes: list[str], missing: list[str]):
    value = values.get(condition.parameter)
    if condition.operator in ("is_missing", "is_present"):
        # Here a missing value IS the answer, never "missing data"
        result = (value is None) == (condition.operator == "is_missing")
        notes.append(f"{condition.parameter} is {'missing' if value is None else 'present'}")
        return result
    if value is None:
        missing.append(condition.parameter)
        return UNKNOWN
    try:
        result = _compare(value, condition.operator, condition.value)
    except TypeError:
        # A value of the wrong type (e.g. text where a number is expected) can't be judged
        missing.append(condition.parameter)
        notes.append(f"{condition.parameter} has an invalid value ({value!r})")
        return UNKNOWN
    expected = condition.value
    shown = ", ".join(map(str, expected)) if isinstance(expected, list) else expected
    notes.append(
        f"{condition.parameter} is {_show(value)} "
        f"({'' if result else 'not '}{OPERATOR_WORDS[condition.operator]} {shown})"
    )
    return result


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    match operator:
        case "greater_than":
            return actual > expected
        case "greater_or_equal":
            return actual >= expected
        case "less_than":
            return actual < expected
        case "less_or_equal":
            return actual <= expected
        case "equals":
            return actual == expected
        case "not_equals":
            return actual != expected
        case "in":
            return actual in expected
        case "not_in":
            return actual not in expected
        case "contains":
            return expected in _as_list(actual)
        case "not_contains":
            return expected not in _as_list(actual)
        case "contains_any":
            return any(item in _as_list(actual) for item in expected)
        case "between":
            low, high = expected
            return low <= actual <= high
    raise ValueError(f"Unknown operator {operator}")


def _as_list(value: Any) -> list:
    if not isinstance(value, list):
        raise TypeError("expected a list")
    return value


def _show(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "none"
    return str(value)
