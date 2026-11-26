import type { ReactNode } from "react";
import { AlertTriangleIcon } from "lucide-react";
import type { Rule } from "@/api/rules";
import { Badge } from "@/components/ui/badge";
import { RuleConditions } from "../RuleConditions/RuleConditions";
import { OUTCOME_LABELS, pagesText, type ParameterLookup } from "../ruleText";

interface Props {
  rule: Rule;
  parameters: ParameterLookup;
  problems?: string[];
  before?: ReactNode; // e.g. the approve checkbox
}

// One rule, readable: what happens, when, and the guideline sentence it comes from
export function RuleItem({ rule, parameters, problems = [], before }: Props) {
  return (
    <li className="flex gap-3 p-3">
      {before}
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={rule.outcome === "decline" ? "destructive" : "secondary"}
          >
            {OUTCOME_LABELS[rule.outcome]}
          </Badge>
          {rule.rule_type === "judgment" && (
            <Badge variant="outline">Underwriter decides</Badge>
          )}
          <span className="font-medium">{rule.description}</span>
        </div>

        <div className="text-sm">
          <span className="text-muted-foreground">When </span>
          {rule.conditions ? (
            <RuleConditions node={rule.conditions} parameters={parameters} />
          ) : (
            <span className="text-destructive">
              no conditions (applies to everyone)
            </span>
          )}
        </div>

        <blockquote className="border-l-2 pl-3 text-xs text-muted-foreground">
          “{rule.source.quote}”
          <span className="ml-1 whitespace-nowrap">
            · {pagesText(rule.source)}
          </span>
        </blockquote>

        {problems.map((problem) => (
          <p
            key={problem}
            className="flex items-center gap-1 text-xs text-destructive"
          >
            <AlertTriangleIcon className="size-3.5 shrink-0" /> {problem}
          </p>
        ))}
      </div>
    </li>
  );
}
