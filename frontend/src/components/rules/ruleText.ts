import type { Condition, ConditionGroup, Outcome, Parameter, Scalar, Source } from "@/api/rules";

export const OUTCOME_LABELS: Record<Outcome, string> = {
  decline: "Decline",
  refer: "Refer to underwriter",
  require_document: "Ask for a document",
};

export const KIND_LABELS: Record<Parameter["kind"], string> = {
  application: "Application form",
  medical: "Medical",
  document: "Documents",
};

export type ParameterLookup = Map<string, Parameter>;

export function isCondition(node: Condition | ConditionGroup): node is Condition {
  return "parameter" in node;
}

// "type_2_diabetes" → "type 2 diabetes"
export function humanize(value: Scalar): string {
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value).replaceAll("_", " ");
}

// The operator field of a condition row: [Age] [is at least] [65]
export const OPERATOR_LABELS: Record<Condition["operator"], string> = {
  greater_than: "is more than",
  greater_or_equal: "is at least",
  less_than: "is less than",
  less_or_equal: "is at most",
  equals: "is",
  not_equals: "is not",
  in: "is one of",
  not_in: "is none of",
  contains: "includes",
  not_contains: "doesn't include",
  contains_any: "includes any of",
  between: "is between",
  is_missing: "is missing",
  is_present: "is provided",
};

// A condition's value as separate values (a list shows each one; none for is_missing / is_present)
export function conditionValues(condition: Condition): Scalar[] {
  const value = condition.value;
  if (value === null || value === undefined) return [];
  return Array.isArray(value) ? value : [value];
}

export function pagesText(source: Source): string {
  if (!source.page) return "page not found";
  return source.last_page ? `pages ${source.page}–${source.last_page}` : `page ${source.page}`;
}

// Every parameter a rule's conditions use
export function usedParameters(node: Condition | ConditionGroup | null | undefined, into = new Set<string>()) {
  if (!node) return into;
  if (isCondition(node)) return into.add(node.parameter);
  node.items.forEach((item) => usedParameters(item, into));
  return into;
}
