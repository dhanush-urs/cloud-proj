type Props = {
  content: string;
};

export function MarkdownView({ content }: Props) {
  const lines = content.split("\n");

  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        if (line.startsWith("# ")) {
          return (
            <h1 key={idx} className="mt-4 text-3xl font-bold text-white">
              {line.replace(/^# /, "")}
            </h1>
          );
        }

        if (line.startsWith("## ")) {
          return (
            <h2 key={idx} className="mt-4 text-xl font-semibold text-white">
              {line.replace(/^## /, "")}
            </h2>
          );
        }

        if (line.startsWith("- ")) {
          return (
            <div key={idx} className="pl-2 text-sm text-slate-300">
              • {line.replace(/^- /, "")}
            </div>
          );
        }

        if (/^\d+\.\s/.test(line)) {
          return (
            <div key={idx} className="pl-2 text-sm text-slate-300">
              {line}
            </div>
          );
        }

        if (!line.trim()) {
          return <div key={idx} className="h-2" />;
        }

        return (
          <p key={idx} className="text-sm leading-7 text-slate-300">
            {line}
          </p>
        );
      })}
    </div>
  );
}
