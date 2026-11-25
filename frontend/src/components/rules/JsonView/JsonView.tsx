import { JsonView as JsonTree, defaultStyles } from "react-json-view-lite";
import "react-json-view-lite/dist/index.css";

// The top level and the parameters / rules lists start open; each item starts closed (click ▸)
const expandLists = (level: number) => level < 2;

// The rules as the backend stores and runs them (the same JSON the API sends and receives)
export function JsonView({ value }: { value: unknown }) {
  return (
    <div className="max-h-[32rem] overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">
      <JsonTree
        data={value as object}
        shouldExpandNode={expandLists}
        clickToExpandNode
        style={{ ...defaultStyles, container: "" }}
      />
    </div>
  );
}
