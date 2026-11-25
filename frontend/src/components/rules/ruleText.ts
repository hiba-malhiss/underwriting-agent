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

function list(values: Scalar[], joiner = "or"): string {
  const words = values.map(humanize);
  return words.length <= 1 ? words.join("") : `${words.slice(0, -1).join(", ")} ${joiner} ${words.at(-1)}`;
}

// One condition as a sentence: "Age is more than 64 years", "Documents provided don't include
// medical report", "HbA1c is missing". Uses the parameter's description when it's known.
export function conditionSentence(condition: Condition, parameters: ParameterLookup): string {
  const parameter = parameters.get(condition.parameter);
  const label = parameter?.description ?? humanize(condition.parameter);
  const unit = parameter?.unit ? ` ${parameter.unit}` : "";
  const value = condition.value;
  const values = Array.isArray(value) ? value : value === null || value === undefined ? [] : [value];

  switch (condition.operator) {
    case "greater_than":
      return `${label} is more than ${humanize(values[0])}${unit}`;
    case "greater_or_equal":
      return `${label} is ${humanize(values[0])}${unit} or more`;
    case "less_than":
      return `${label} is less than ${humanize(values[0])}${unit}`;
    case "less_or_equal":
      return `${label} is ${humanize(values[0])}${unit} or less`;
    case "between":
      return `${label} is between ${humanize(values[0])} and ${humanize(values[1])}${unit}`;
    case "equals":
      return typeof values[0] === "boolean"
        ? `${label}: ${humanize(values[0])}`
        : `${label} is ${humanize(values[0])}`;
    case "not_equals":
      return `${label} is not ${humanize(values[0])}`;
    case "in":
      return `${label} is ${list(values)}`;
    case "not_in":
      return `${label} is not ${list(values)}`;
    case "contains":
      return `${label} include ${humanize(values[0])}`;
    case "not_contains":
      return `${label} don't include ${humanize(values[0])}`;
    case "contains_any":
      return `${label} include ${list(values)}`;
    case "is_missing":
      return `${label} is missing`;
    case "is_present":
      return `${label} is provided`;
    default:
      return `${label} ${condition.operator} ${list(values, "and")}`;
  }
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
