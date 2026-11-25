// The rules as the backend stores and runs them (the same JSON the API sends and receives)
export function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[32rem] overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-relaxed">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
