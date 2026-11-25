import type { Parameter } from "@/api/rules";
import { Badge } from "@/components/ui/badge";
import { KIND_LABELS } from "../ruleText";

// Parameters as badges: the readable description, with where the value comes from on hover
export function ParameterBadges({ parameters }: { parameters: Parameter[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {parameters.map((p) => (
        <Badge
          key={p.name}
          variant="outline"
          title={[
            p.name,
            KIND_LABELS[p.kind],
            p.allowed_values?.join(", "),
          ]
            .filter(Boolean)
            .join(" · ")}
        >
          {p.description}
          {p.unit && <span className="text-muted-foreground">{p.unit}</span>}
        </Badge>
      ))}
    </div>
  );
}
