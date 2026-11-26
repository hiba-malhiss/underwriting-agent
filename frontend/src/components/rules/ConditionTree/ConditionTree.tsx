import type { Condition, ConditionGroup } from "@/api/rules";
import { cn } from "@/lib/utils";
import {
  OPERATOR_LABELS,
  conditionValues,
  humanize,
  isCondition,
  type ParameterLookup,
} from "../ruleText";

interface Props {
  node: Condition | ConditionGroup;
  parameters: ParameterLookup;
}

// A rule's conditions like a rule builder: each condition is a row of fields
// [parameter] [operator] [value], and a group joins its rows with AND / OR (groups can nest)
export function ConditionTree({ node, parameters }: Props) {
  if (isCondition(node)) return <ConditionRow condition={node} parameters={parameters} />;
  if (node.items.length === 1)
    return <ConditionTree node={node.items[0]} parameters={parameters} />;

  const joiner = node.match === "all" ? "AND" : "OR";
  return (
    <div className="space-y-1.5 rounded-md border-l-2 border-primary/40 bg-muted/20 py-1.5 pr-1.5 pl-3">
      <p className="text-[11px] font-semibold tracking-wide text-muted-foreground">
        {node.match === "all" ? "ALL of these" : "ANY of these"}
      </p>
      {node.items.map((item, index) => (
        <div key={index} className="space-y-1.5">
          {index > 0 && <p className="text-[11px] font-semibold text-primary">{joiner}</p>}
          <ConditionTree node={item} parameters={parameters} />
        </div>
      ))}
    </div>
  );
}

function ConditionRow({
  condition,
  parameters,
}: {
  condition: Condition;
  parameters: ParameterLookup;
}) {
  const parameter = parameters.get(condition.parameter);
  const values = conditionValues(condition);
  const unit = parameter?.unit;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Field title={parameter?.description} className="font-medium">
        {humanize(condition.parameter)}
      </Field>
      <Field muted>{OPERATOR_LABELS[condition.operator]}</Field>
      {condition.operator === "between" ? (
        <>
          <Field>{humanize(values[0])}</Field>
          <span className="text-xs text-muted-foreground">and</span>
          <Field>
            {humanize(values[1])}
            {unit && ` ${unit}`}
          </Field>
        </>
      ) : (
        values.map((value) => (
          <Field key={String(value)}>
            {humanize(value)}
            {unit && ` ${unit}`}
          </Field>
        ))
      )}
    </div>
  );
}

// One read-only field, like an input in a rule builder
function Field({
  children,
  muted,
  title,
  className,
}: {
  children: React.ReactNode;
  muted?: boolean;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex h-7 items-center rounded-md border bg-background px-2 text-xs shadow-xs",
        muted && "bg-muted text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}
