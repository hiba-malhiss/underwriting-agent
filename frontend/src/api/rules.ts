import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "./http";

// ---- Shapes: mirror backend rules/models.py and rules/schemas.py ----

export type ValueType =
  "number" | "boolean" | "enum" | "list" | "text" | "date";
// Where the value comes from: the form, medical documents, which files were provided, or code
export type ParameterKind = "application" | "medical" | "document";
export type Outcome = "decline" | "refer" | "require_document";
export type Scalar = number | boolean | string;

export interface Source {
  document: string;
  page?: number | null;
  last_page?: number | null; // when the quote runs onto the next page
  quote: string;
}

export interface Parameter {
  name: string;
  kind: ParameterKind;
  value_type: ValueType;
  description: string;
  allowed_values?: string[] | null;
  unit?: string | null;
}

export interface Condition {
  parameter: string;
  operator: string; // greater_than, equals, contains, between, is_missing…
  value?: Scalar | Scalar[] | null; // none for is_missing / is_present; [low, high] for between
}

// "all" = AND, "any" = OR; an item can be another group
export interface ConditionGroup {
  match: "all" | "any";
  items: (Condition | ConditionGroup)[];
}

export interface Rule {
  name: string;
  description: string;
  rule_type: "automatic" | "judgment";
  conditions?: ConditionGroup | null;
  outcome: Outcome;
  source: Source;
}

export interface RulebookVersion {
  version: number;
  approved_at: string;
  note: string | null;
  parameters: Parameter[];
  rules: Rule[];
}

export interface Proposal {
  based_on_version: number | null;
  document: string;
  parameters: { parameter: Parameter; problems: string[] }[];
  rules: { rule: Rule; problems: string[] }[];
  skipped: string[];
  repair_rounds: number; // how many times the model was asked to fix its answer
}

export interface SaveVersionRequest {
  based_on_version: number | null;
  parameters: Parameter[];
  rules: Rule[];
  note?: string;
}

// ---- HTTP ----

export async function getCurrentRulebook() {
  return (await http.get<RulebookVersion | null>("/rules/current")).data;
}

// Slow (30–60 s): the document is read, then the LLM suggests rules
export async function proposeRules(document: string) {
  return (await http.post<Proposal>("/rules/proposals", { document })).data;
}

export async function saveRuleVersion(body: SaveVersionRequest) {
  return (await http.post<RulebookVersion>("/rules/versions", body)).data;
}

// ---- TanStack Query ----

export const currentRulebookKey = ["rules", "current"] as const;

export function useCurrentRulebook() {
  return useQuery({
    queryKey: currentRulebookKey,
    queryFn: getCurrentRulebook,
  });
}

export function useProposeRules() {
  return useMutation({ mutationFn: proposeRules });
}

// Resolves after the current version has reloaded
export function useSaveRuleVersion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveRuleVersion,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: currentRulebookKey }),
  });
}
