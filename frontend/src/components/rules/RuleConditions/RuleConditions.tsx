import type { Condition, ConditionGroup } from "@/api/rules";
import { conditionSentence, isCondition, type ParameterLookup } from "../ruleText";

interface Props {
  node: Condition | ConditionGroup;
  parameters: ParameterLookup;
}

// A rule's conditions as plain sentences: one line, or "all of these" / "any of these" lists
// (nested groups are indented lists)
export function RuleConditions({ node, parameters }: Props) {
  if (isCondition(node)) return <span>{conditionSentence(node, parameters)}</span>;
  if (node.items.length === 1) return <RuleConditions node={node.items[0]} parameters={parameters} />;

  return (
    <div>
      <span className="font-medium">{node.match === "all" ? "All of these:" : "Any of these:"}</span>
      <ul className="mt-0.5 list-disc space-y-0.5 pl-5">
        {node.items.map((item, index) => (
          <li key={index}>
            <RuleConditions node={item} parameters={parameters} />
          </li>
        ))}
      </ul>
    </div>
  );
}
