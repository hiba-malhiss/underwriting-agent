import type { RulebookVersion } from "@/api/rules";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonView } from "../JsonView/JsonView";
import { conditionsText, OUTCOME_LABELS, pagesText } from "../ruleText";

interface Props {
  current: RulebookVersion | null | undefined;
  loading: boolean;
  error: string | null;
}

// The approved rules applicants are checked against
export function CurrentRules({ current, loading, error }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Current rules{current ? ` · version ${current.version}` : ""}</CardTitle>
        <CardDescription>
          {current
            ? `Approved ${new Date(current.approved_at).toLocaleString()} · ${current.parameters.length} parameters · ${current.rules.length} rules`
            : "Applicants are checked against the approved rules shown here."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <p className="text-sm text-destructive">Couldn't load the rules: {error}</p>
        ) : loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !current ? (
          <p className="text-sm text-muted-foreground">
            No rules yet. Upload guidelines, then click "Suggest rules" on the file.
          </p>
        ) : (
          <Tabs defaultValue="ui">
            <TabsList>
              <TabsTrigger value="ui">UI</TabsTrigger>
              <TabsTrigger value="code">Code</TabsTrigger>
            </TabsList>
            <TabsContent value="ui" className="space-y-4 pt-2">
                <div className="flex flex-wrap gap-1.5">
                  {current.parameters.map((p) => (
                    <Badge key={p.name} variant="outline" title={p.description}>
                      {p.name}
                      <span className="text-muted-foreground">
                        {p.value_type}
                        {p.unit ? ` · ${p.unit}` : ""}
                      </span>
                    </Badge>
                  ))}
                </div>
                <ul className="divide-y">
                  {current.rules.map((rule) => (
                    <li key={rule.name} className="space-y-1 py-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={rule.outcome === "decline" ? "destructive" : "secondary"}>
                          {OUTCOME_LABELS[rule.outcome]}
                        </Badge>
                        <span className="font-medium">{rule.description}</span>
                      </div>
                      <p className="font-mono text-xs text-muted-foreground">
                        {conditionsText(rule.conditions)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        “{rule.source.quote}” · {rule.source.document}, {pagesText(rule.source)}
                      </p>
                    </li>
                  ))}
                </ul>
            </TabsContent>
            <TabsContent value="code" className="pt-2">
              <JsonView value={{ parameters: current.parameters, rules: current.rules }} />
            </TabsContent>
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
