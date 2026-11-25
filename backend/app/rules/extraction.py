"""Check rules and parameters suggested by the LLM.

Steps:
1. Remove duplicates: rules by what they do (not their name), parameters by name + type.
2. Verify each rule's quote against the document (parameters have no quote).
3. Validate the combined rulebook; flag new parameters that no rule uses.
4. Return suggestions and problems for human review.

Nothing is saved here.
"""

from dataclasses import dataclass, field

from app.infrastructure.document_reader import DocumentText
from app.rules.models import (
    Condition,
    ConditionGroup,
    Parameter,
    Rule,
    Rulebook,
    Source,
)
from app.rules.validation import find_problems


@dataclass(frozen=True)
class SuggestedParameter:
    parameter: Parameter
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SuggestedRule:
    rule: Rule
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Proposal:
    based_on_version: int | None
    document: str
    parameters: list[SuggestedParameter]
    rules: list[SuggestedRule]
    skipped: list[str]


def check_suggestions(
    suggested: Rulebook,
    current: Rulebook | None,
    text: DocumentText,
    document_name: str,
    based_on_version: int | None,
) -> Proposal:

    current = current or Rulebook(parameters=[], rules=[])

    # 1. Find new parameters and rules.
    parameters, skipped_params, param_errors = check_parameters(
        suggested.parameters,
        current.parameters,
    )

    rules, skipped_rules, rule_errors = check_rules(
        suggested.rules,
        current.rules,
    )

    # 2. Verify rule quotes and get correct page numbers.
    located_rules = [locate_source(r, text, document_name) for r in rules]

    # 3. Validate old + new rules together.
    combined = Rulebook(
        parameters=current.parameters + parameters,
        rules=current.rules + [r for r, _ in located_rules],
    )

    validation_errors = collect_validation_errors(
        combined,
        {**param_errors, **rule_errors},
    )
    unused_errors = flag_unused_parameters(parameters, combined.rules)

    # 4. Prepare suggestions for human review.
    return Proposal(
        based_on_version=based_on_version,
        document=document_name,
        parameters=[
            SuggestedParameter(
                p,
                merge_errors(
                    param_errors.get(f"parameter {p.name}", []),
                    validation_errors.get(f"parameter {p.name}", []),
                    unused_errors.get(f"parameter {p.name}", []),
                ),
            )
            for p in parameters
        ],
        rules=[
            SuggestedRule(
                r,
                merge_errors(
                    quote_errors,
                    rule_errors.get(f"rule {r.name}", []),
                    validation_errors.get(f"rule {r.name}", []),
                ),
            )
            for r, quote_errors in located_rules
        ],
        skipped=skipped_params + skipped_rules,
    )


def check_parameters(
    suggested: list[Parameter],
    current: list[Parameter],
):
    """Find new parameters and flag name conflicts."""

    existing_by_name = {p.name: p for p in current}

    new_parameters = []
    skipped = []
    errors = {}

    for parameter in suggested:
        name = parameter.name
        existing = existing_by_name.get(name)

        # Same name and definition -> skip.
        if existing is not None and same_parameter(existing, parameter):
            skipped.append(f"parameter {name} (already in the rulebook)")
            continue

        problems = []

        # Same name, different definition -> flag.
        if existing is not None:
            problems.append(
                f"the name '{name}' is already used by a "
                f"different parameter ({existing.value_type}); "
                "pick another name or reuse it"
            )

        new_parameters.append(parameter)

        if problems:
            errors[f"parameter {name}"] = problems

    return new_parameters, skipped, errors


def same_parameter(a: Parameter, b: Parameter) -> bool:
    return a.value_type == b.value_type and sorted(a.allowed_values or []) == sorted(
        b.allowed_values or []
    )


def check_rules(
    suggested: list[Rule],
    current: list[Rule],
):
    """Compare rules by behavior, not their names."""

    seen = {rule_key(rule): f"current rule {rule.name}" for rule in current}

    existing_names = {r.name for r in current}

    new_rules = []
    skipped = []
    errors = {}

    for rule in suggested:
        key = rule_key(rule)

        # Same conditions and outcome -> duplicate.
        if key in seen:
            skipped.append(f"rule {rule.name} (same as {seen[key]})")
            continue

        seen[key] = f"suggested rule {rule.name}"

        # Same name but different rule -> flag.
        if rule.name in existing_names:
            errors.setdefault(f"rule {rule.name}", []).append(
                f"the name '{rule.name}' is already used by a different rule; rename it"
            )

        new_rules.append(rule)

    return new_rules, skipped, errors


def rule_key(rule: Rule) -> tuple:
    """Build a key representing what the rule does."""

    if rule.rule_type == "judgment" or not rule.conditions:
        return (
            "judgment",
            rule.outcome,
            normalize_quote(rule.source.quote),
        )

    return (
        "automatic",
        rule.outcome,
        condition_key(rule.conditions),
    )


def condition_key(node: Condition | ConditionGroup) -> tuple:
    """Normalize conditions so their order doesn't matter."""

    if isinstance(node, Condition):
        return (
            "condition",
            node.parameter,
            node.operator,
            value_key(node.value),
        )

    is_all = bool(node.all_of)
    items = node.all_of if is_all else (node.any_of or [])

    keys = sorted(
        (condition_key(item) for item in items),
        key=repr,
    )

    if len(keys) == 1:
        return keys[0]

    return (
        "all_of" if is_all else "any_of",
        tuple(keys),
    )


def value_key(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, list):
        return tuple(sorted(value))

    return value


def normalize_quote(quote: str) -> str:
    return " ".join(quote.split()).lower().strip(" .")


def locate_source(
    item: Rule,
    text: DocumentText,
    document_name: str,
):
    """Verify a rule's quote and find its actual document page."""

    pages = text.locate(item.source.quote)

    if pages is None:
        source = Source(
            document=document_name,
            quote=item.source.quote,
        )
        errors = ["quote not found in the document (made up or paraphrased?)"]

    else:
        first, last = pages

        source = Source(
            document=document_name,
            page=first,
            last_page=last if last != first else None,
            quote=item.source.quote,
        )
        errors = []

    updated_item = item.model_copy(update={"source": source})

    return updated_item, errors


def flag_unused_parameters(
    new_parameters: list[Parameter],
    rules: list[Rule],
) -> dict[str, list[str]]:
    """A new parameter that no rule uses is probably made up or left over."""

    used = {
        condition.parameter
        for rule in rules
        if rule.conditions
        for condition in iter_conditions(rule.conditions)
    }

    return {
        f"parameter {p.name}": ["not used by any rule"]
        for p in new_parameters
        if p.name not in used
    }


def iter_conditions(node: Condition | ConditionGroup):
    """Every condition in a (nested) group."""

    if isinstance(node, Condition):
        yield node
        return

    for item in (node.all_of or []) + (node.any_of or []):
        yield from iter_conditions(item)


def collect_validation_errors(
    rulebook: Rulebook,
    existing_errors: dict[str, list[str]],
):
    """Group validation errors by parameter/rule."""

    errors = {}

    for problem in find_problems(rulebook):
        # Avoid repeating a name conflict already explained.
        if problem.message == "is defined twice" and existing_errors.get(problem.where):
            continue

        errors.setdefault(problem.where, []).append(problem.message)

    return errors


def merge_errors(*groups: list[str]) -> list[str]:
    """Combine problems without duplicate messages."""

    all_errors = [error for group in groups for error in group]

    return list(dict.fromkeys(all_errors))
