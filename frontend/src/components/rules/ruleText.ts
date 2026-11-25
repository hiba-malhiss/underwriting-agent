import type { Condition, ConditionGroup, Outcome, Source } from "@/api/rules";

// How each operator reads, e.g. "age more than 65" (mirrors backend rules/evaluator.py)
const OPERATOR_WORDS: Record<string, string> = {
  greater_than: "more than",
  greater_or_equal: "at least",
  less_than: "less than",
  less_or_equal: "at most",
  equals: "is",
  not_equals: "is not",
  in: "is one of",
  not_in: "is none of",
  contains: "includes",
  not_contains: "excludes",
  contains_any: "includes any of",
};

export const OUTCOME_LABELS: Record<Outcome, string> = {
  decline: "Decline",
  refer: "Refer",
  require_document: "Require document",
};

function isCondition(node: Condition | ConditionGroup): node is Condition {
  return "parameter" in node;
}

function valueText(value: Condition["value"]): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

// A rule's conditions in plain words: "age more than 65 AND (smoker is yes OR bmi more than 30)"
export function conditionsText(node: Condition | ConditionGroup | null | undefined, nested = false): string {
  if (!node) return "Underwriter's judgment";
  if (isCondition(node)) {
    return `${node.parameter} ${OPERATOR_WORDS[node.operator] ?? node.operator} ${valueText(node.value)}`;
  }
  const text = node.items
    .map((item) => conditionsText(item, true))
    .join(node.match === "all" ? " AND " : " OR ");
  return nested && node.items.length > 1 ? `(${text})` : text;
}

export function pagesText(source: Source): string {
  if (!source.page) return "page not found";
  return source.last_page ? `pages ${source.page}–${source.last_page}` : `page ${source.page}`;
}
