type Props = {
  message: string | null;
};

export function ActionConsole({ message }: Props) {
  if (!message) return null;

  return (
    <div className="rounded-xl border border-slate-800 bg-black p-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-emerald-400">
        Action Console
      </div>
      <pre className="text-xs text-slate-300">{message}</pre>
    </div>
  );
}
