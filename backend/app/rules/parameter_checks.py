"""The LLM's suggested parameters, checked against the current rulebook, which is the registry
(like AUI's parameters.aui.json): there are no built-in parameters, every one comes from the
guidelines.

For each suggested parameter:
- not in the rulebook yet: kept (it's new).
- in the rulebook with the same definition: skipped.
- in the rulebook with the same kind and type but new allowed values: kept as an update (a list
  of plans, conditions or documents grows), flagged for review.
- in the rulebook with a different definition: kept and flagged as a name conflict.
"""

from dataclasses import dataclass, field

from app.rules.models import Condition, ConditionGroup, Parameter, Rule

# Starts the note on a parameter that gains allowed values: a note for the reviewer, not a mistake
# for the model to fix
NEW_ALLOWED_VALUES = "new allowed values"


@dataclass
class ParameterCheck:
    parameters: list[Parameter] = field(default_factory=list)  # to add or update
    skipped: list[str] = field(default_factory=list)
    errors: dict[str, list[str]] = field(default_factory=dict)  # "parameter x" → problems

    def flag(self, name: str, problem: str) -> None:
        self.errors.setdefault(f"parameter {name}", []).append(problem)


def check_parameters(suggested: list[Parameter], current: list[Parameter]) -> ParameterCheck:
    check = ParameterCheck()
    current_by_name = {p.name: p for p in current}

    for parameter in suggested:
        existing = current_by_name.get(parameter.name)
        if existing is None:
            check.parameters.append(parameter)
        elif same_definition(existing, parameter):
            check.skipped.append(f"parameter {parameter.name} (already in the rulebook)")
        elif same_shape(existing, parameter):
            _new_values(existing, parameter, check)
        else:
            check.parameters.append(parameter)
            check.flag(
                parameter.name,
                f"the name '{parameter.name}' is already used by a different parameter "
                f"({existing.kind}, {existing.value_type}); pick another name or reuse it",
            )
    return check


def _new_values(existing: Parameter, parameter: Parameter, check: ParameterCheck) -> None:
    known = existing.allowed_values or []
    extra = [v for v in parameter.allowed_values or [] if v not in known]
    if not extra:
        check.skipped.append(f"parameter {parameter.name} (already in the rulebook)")
        return
    check.parameters.append(existing.model_copy(update={"allowed_values": known + extra}))
    check.flag(parameter.name, f"{NEW_ALLOWED_VALUES}: {', '.join(extra)}")


def same_shape(a: Parameter, b: Parameter) -> bool:
    return (a.kind, a.value_type) == (b.kind, b.value_type)


def same_definition(a: Parameter, b: Parameter) -> bool:
    return same_shape(a, b) and sorted(a.allowed_values or []) == sorted(b.allowed_values or [])


def merge_parameters(current: list[Parameter], additions: list[Parameter]) -> list[Parameter]:
    """current + additions, where an addition with the same name and shape REPLACES the current
    one (that's how a list gains new allowed values). Other clashes are kept, so the rulebook
    checks report them as "defined twice"."""
    merged = {p.name: p for p in current}
    clashes = []
    for parameter in additions:
        existing = merged.get(parameter.name)
        if existing is None or same_shape(existing, parameter):
            merged[parameter.name] = parameter
        else:
            clashes.append(parameter)
    return list(merged.values()) + clashes


def used_parameters(rules: list[Rule]) -> set[str]:
    return {
        condition.parameter
        for rule in rules
        if rule.conditions
        for condition in iter_conditions(rule.conditions)
    }


def iter_conditions(node: Condition | ConditionGroup):
    """Every condition in a (nested) group."""
    if isinstance(node, Condition):
        yield node
        return
    for item in node.items:
        yield from iter_conditions(item)
