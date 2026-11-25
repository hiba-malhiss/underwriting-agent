import { useMemo, useState } from "react";
import { AlertTriangleIcon, SaveIcon } from "lucide-react";
import type { Condition, ConditionGroup, Parameter, Proposal, Rule } from "@/api/rules";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonView } from "../JsonView/JsonView";
import { conditionsText, OUTCOME_LABELS, pagesText } from "../ruleText";

interface Props {
  proposal: Proposal;
  saving: boolean;
  onSave: (rules: Rule[], parameters: Parameter[]) => Promise<unknown>;
  onCancel: () => void;
}

// Every parameter a rule's conditions use
function usedParameters(node: Condition | ConditionGroup | null | undefined, into: Set<string>) {
  if (!node) return into;
  if ("parameter" in node) return into.add(node.parameter);
  node.items.forEach((item) => usedParameters(item, into));
  return into;
}

// The LLM's suggestions: a human approves or rejects each rule, then saves
export function ProposalReview({ proposal, saving, onSave, onCancel }: Props) {
  // Rules without problems start approved; rules with problems start rejected
  const [approved, setApproved] = useState<Set<string>>(
    () => new Set(proposal.rules.filter((r) => r.problems.length === 0).map((r) => r.rule.name)),
  );

  const toggle = (name: string) =>
    setApproved((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  const approvedRules = proposal.rules.filter((r) => approved.has(r.rule.name)).map((r) => r.rule);
  // New parameters are saved only if an approved rule uses them
  const neededParameters = useMemo(() => {
    const used = new Set<string>();
    approvedRules.forEach((rule) => usedParameters(rule.conditions, used));
    return proposal.parameters.map((p) => p.parameter).filter((p) => used.has(p.name));
  }, [approvedRules, proposal.parameters]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Suggested rules · {proposal.document}</CardTitle>
        <CardDescription>
          The AI suggests, you decide. Check each rule against its quote, then save. Rules with
          problems start unticked.
          {proposal.based_on_version !== null &&
            ` Saving adds them to version ${proposal.based_on_version} (nothing is removed).`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs defaultValue="ui">
          <TabsList>
            <TabsTrigger value="ui">UI</TabsTrigger>
            <TabsTrigger value="code">Code</TabsTrigger>
          </TabsList>
          <TabsContent value="ui" className="pt-2">
            {proposal.rules.length === 0 ? (
              <p className="text-sm text-muted-foreground">No new rules found in this document.</p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {proposal.rules.map(({ rule, problems }) => (
                  <li key={rule.name} className="flex gap-3 p-3">
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-primary"
                      aria-label={`Approve ${rule.name}`}
                      checked={approved.has(rule.name)}
                      onChange={() => toggle(rule.name)}
                    />
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={rule.outcome === "decline" ? "destructive" : "secondary"}>
                          {OUTCOME_LABELS[rule.outcome]}
                        </Badge>
                        <span className="font-medium">{rule.description}</span>
                      </div>
                      <p className="font-mono text-xs text-muted-foreground">
                        {conditionsText(rule.conditions)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        “{rule.source.quote}” · {pagesText(rule.source)}
                      </p>
                      {problems.map((problem) => (
                        <p key={problem} className="flex items-center gap-1 text-xs text-destructive">
                          <AlertTriangleIcon className="size-3.5" /> {problem}
                        </p>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="code" className="space-y-2 pt-2">
            <p className="text-sm text-muted-foreground">
              What the Save button sends: the approved rules and the new parameters they use.
            </p>
            <JsonView value={{ parameters: neededParameters, rules: approvedRules }} />
          </TabsContent>
        </Tabs>

        {neededParameters.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-sm font-medium">New parameters saved with the approved rules</p>
            <div className="flex flex-wrap gap-1.5">
              {neededParameters.map((p) => (
                <Badge key={p.name} variant="outline" title={p.description}>
                  {p.name}
                  <span className="text-muted-foreground">{p.value_type}</span>
                </Badge>
              ))}
            </div>
          </div>
        )}

        {proposal.skipped.length > 0 && (
          <details className="text-sm text-muted-foreground">
            <summary className="cursor-pointer">
              Already in the rules ({proposal.skipped.length})
            </summary>
            <ul className="mt-1 list-disc pl-5">
              {proposal.skipped.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </details>
        )}

        <div className="flex gap-2">
          <Button
            disabled={saving || approvedRules.length === 0}
            onClick={() => void onSave(approvedRules, neededParameters)}
          >
            <SaveIcon />
            {saving ? "Saving…" : `Save ${approvedRules.length} rules as a new version`}
          </Button>
          <Button variant="outline" disabled={saving} onClick={onCancel}>
            Discard
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
