type Props = {
  content: string;
};

export function CodeBlockViewer({ content }: Props) {
  const lines = content.split("\n");

  return (
    <div className="overflow-auto rounded-xl border border-slate-800 bg-slate-950">
      <div className="min-w-[900px]">
        {lines.map((line, index) => (
          <div
            key={index}
            className="grid grid-cols-[72px_1fr] border-b border-slate-900 last:border-b-0"
          >
            <div className="select-none bg-slate-900 px-3 py-1 text-right text-xs text-slate-500">
              {index + 1}
            </div>
            <pre className="overflow-x-auto px-4 py-1 text-xs leading-6 text-slate-300">
              {line || " "}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
}
