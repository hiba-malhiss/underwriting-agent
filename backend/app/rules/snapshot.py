"""A short summary of the current rulebook for the LLM, written by code (like AUI's "Agent
Snapshot", but AUI needs an LLM for it because its configs come in many kinds; ours have one fixed
shape, so code writes it exactly and for free).

One line per parameter and one per rule, instead of the full JSON:

    PARAMETERS
    - age (application, number, years): Applicant's age
    - plan (application, enum: essential | enhanced | family): Plan applied for

    RULES
    - applicant_over_64: IF age greater_than 64 THEN decline

Enough for the LLM to reuse parameter names and see which rules exist, in far fewer tokens.
"""

import json

from app.rules.models import Condition, ConditionGroup, Parameter, Rule, Rulebook

_JOINERS = {"all": " AND ", "any": " OR "}


def snapshot(rulebook: Rulebook | None) -> str:
    if rulebook is None or not (rulebook.parameters or rulebook.rules):
        return "(empty: no parameters or rules yet)"
    lines = ["PARAMETERS", *(_parameter_line(p) for p in rulebook.parameters)]
    lines += ["", "RULES", *(_rule_line(r) for r in rulebook.rules)]
    return "\n".join(lines)


def _parameter_line(parameter: Parameter) -> str:
    details = [parameter.kind, parameter.value_type]
    if parameter.allowed_values:
        details[-1] += ": " + " | ".join(parameter.allowed_values)
    if parameter.unit:
        details.append(parameter.unit)
    return f"- {parameter.name} ({', '.join(details)}): {parameter.description}"


def _rule_line(rule: Rule) -> str:
    if rule.conditions is None:  # judgment: no conditions, the description says what it's about
        return f"- {rule.name}: JUDGMENT {rule.description} THEN {rule.outcome}"
    return f"- {rule.name}: IF {_conditions(rule.conditions)} THEN {rule.outcome}"


def _conditions(node: Condition | ConditionGroup, nested: bool = False) -> str:
    """age greater_than 64, (a AND (b OR c)): the operator names the LLM writes itself."""
    if isinstance(node, Condition):
        value = "" if node.value is None else " " + json.dumps(node.value)
        return f"{node.parameter} {node.operator}{value}"
    joined = _JOINERS[node.match].join(_conditions(item, nested=True) for item in node.items)
    return f"({joined})" if nested and len(node.items) > 1 else joined
