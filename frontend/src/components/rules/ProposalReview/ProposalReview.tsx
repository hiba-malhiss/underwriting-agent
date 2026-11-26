import { useMemo, useState } from "react";
import { SaveIcon } from "lucide-react";
import type { Parameter, Proposal, Rule } from "@/api/rules";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonView } from "../JsonView/JsonView";
import { ParameterBadges } from "../ParameterBadges/ParameterBadges";
import { RuleItem } from "../RuleItem/RuleItem";
import { usedParameters } from "../ruleText";

interface Props {
  proposal: Proposal;
  currentParameters: Parameter[]; // to describe rules that use existing parameters
  saving: boolean;
  onSave: (rules: Rule[], parameters: Parameter[]) => Promise<unknown>;
  onCancel: () => void;
}

// The LLM's suggestions: a human approves or rejects each rule, then saves
export function ProposalReview({
  proposal,
  currentParameters,
  saving,
  onSave,
  onCancel,
}: Props) {
  // Rules without problems start approved; rules with problems start rejected
  const [approved, setApproved] = useState<Set<string>>(
    () =>
      new Set(
        proposal.rules
          .filter((r) => r.problems.length === 0)
          .map((r) => r.rule.name),
      ),
  );

  const toggle = (name: string) =>
    setApproved((current) => {
      const next = new Set(current);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });

  const parameters = useMemo(
    () =>
      new Map(
        [
          ...currentParameters,
          ...proposal.parameters.map((p) => p.parameter),
        ].map((p) => [p.name, p]),
      ),
    [currentParameters, proposal.parameters],
  );
  const approvedRules = proposal.rules
    .filter((r) => approved.has(r.rule.name))
    .map((r) => r.rule);
  // Suggested parameters are saved only if an approved rule uses them
  const neededParameters = useMemo(() => {
    const used = new Set<string>();
    approvedRules.forEach((rule) => usedParameters(rule.conditions, used));
    return proposal.parameters
      .map((p) => p.parameter)
      .filter((p) => used.has(p.name));
  }, [approvedRules, proposal.parameters]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Suggested rules · {proposal.document}</CardTitle>
        <CardDescription>
          The AI suggests, you decide. Check each rule against its quote, then
          save. Rules with problems start unticked.
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
          <TabsContent value="ui" className="space-y-4 pt-2">
            {proposal.rules.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No new rules found in this document.
              </p>
            ) : (
              <ul className="space-y-3">
                {proposal.rules.map(({ rule, problems }) => (
                  <RuleItem
                    key={rule.name}
                    rule={rule}
                    parameters={parameters}
                    problems={problems}
                    before={
                      <input
                        type="checkbox"
                        className="mt-1 size-4 accent-primary"
                        aria-label={`Approve ${rule.description}`}
                        checked={approved.has(rule.name)}
                        onChange={() => toggle(rule.name)}
                      />
                    }
                  />
                ))}
              </ul>
            )}

            {proposal.missed.length > 0 && (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                <p className="font-medium">
                  The guidelines require these, but no rule was written for them
                  ({proposal.missed.length})
                </p>
                <ul className="mt-1 list-disc pl-5">
                  {proposal.missed.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {neededParameters.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-sm font-medium">
                  Parameters saved with the approved rules
                </p>
                <ParameterBadges parameters={neededParameters} />
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
          </TabsContent>
          <TabsContent value="code" className="space-y-2 pt-2">
            <p className="text-sm text-muted-foreground">
              What the Save button sends: the approved rules and the parameters
              they use.
            </p>
            <JsonView
              value={{ parameters: neededParameters, rules: approvedRules }}
            />
          </TabsContent>
        </Tabs>

        <div className="flex gap-2">
          <Button
            disabled={saving || approvedRules.length === 0}
            onClick={() => void onSave(approvedRules, neededParameters)}
          >
            <SaveIcon />
            {saving
              ? "Saving…"
              : `Save ${approvedRules.length} rules as a new version`}
          </Button>
          <Button variant="outline" disabled={saving} onClick={onCancel}>
            Discard
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
