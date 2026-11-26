import type { RulebookVersion } from "@/api/rules";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JsonView } from "../JsonView/JsonView";
import { ParameterBadges } from "../ParameterBadges/ParameterBadges";
import { RuleItem } from "../RuleItem/RuleItem";

interface Props {
  current: RulebookVersion | null | undefined;
  loading: boolean;
  error: string | null;
}

// The approved rules applicants are checked against
export function CurrentRules({ current, loading, error }: Props) {
  const parameters = new Map((current?.parameters ?? []).map((p) => [p.name, p]));

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
      <CardContent>
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
              <ParameterBadges parameters={current.parameters} />
              <ul className="space-y-3">
                {current.rules.map((rule) => (
                  <RuleItem key={rule.name} rule={rule} parameters={parameters} />
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
