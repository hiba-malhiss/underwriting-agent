import type { ReactNode } from "react";
import { AlertTriangleIcon } from "lucide-react";
import type { Rule } from "@/api/rules";
import { Badge } from "@/components/ui/badge";
import { ConditionTree } from "../ConditionTree/ConditionTree";
import { OUTCOME_LABELS, type ParameterLookup } from "../ruleText";
import { SourceQuote } from "../SourceQuote/SourceQuote";

interface Props {
  rule: Rule;
  parameters: ParameterLookup;
  problems?: string[];
  before?: ReactNode; // e.g. the approve checkbox
}

// One rule, like a rule engine shows it: IF [conditions] THEN [outcome], with the guideline
// sentence it comes from (click it to see it in the document)
export function RuleItem({ rule, parameters, problems = [], before }: Props) {
  return (
    <li className="space-y-3 rounded-lg border bg-card p-4">
      <div className="flex items-start gap-3">
        {before}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{rule.description}</span>
            {rule.rule_type === "judgment" && <Badge variant="outline">Underwriter decides</Badge>}
          </div>
          <code className="text-xs text-muted-foreground">{rule.name}</code>
        </div>
      </div>

      <dl className="grid grid-cols-[4.5rem_1fr] items-start gap-x-3 gap-y-3 text-sm">
        <Keyword>IF</Keyword>
        <dd className="min-w-0">
          {rule.conditions ? (
            <ConditionTree node={rule.conditions} parameters={parameters} />
          ) : (
            <span className="text-destructive">no conditions (applies to everyone)</span>
          )}
        </dd>

        <Keyword>THEN</Keyword>
        <dd>
          <Badge variant={rule.outcome === "decline" ? "destructive" : "secondary"}>
            {OUTCOME_LABELS[rule.outcome]}
          </Badge>
        </dd>

        <Keyword>SOURCE</Keyword>
        <dd className="min-w-0">
          <SourceQuote source={rule.source} />
        </dd>
      </dl>

      {problems.map((problem) => (
        <p key={problem} className="flex items-center gap-1 text-xs text-destructive">
          <AlertTriangleIcon className="size-3.5 shrink-0" /> {problem}
        </p>
      ))}
    </li>
  );
}

function Keyword({ children }: { children: ReactNode }) {
  return (
    <dt className="pt-1.5 text-[11px] font-semibold tracking-wider text-muted-foreground">
      {children}
    </dt>
  );
}
