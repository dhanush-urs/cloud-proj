type Props = {
  title?: string;
  description?: string;
};

export function LoadingCard({
  title = "Loading...",
  description = "Fetching data from RepoBrain.",
}: Props) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6">
      <div className="animate-pulse space-y-3">
        <div className="h-5 w-40 rounded bg-slate-800" />
        <div className="h-4 w-72 rounded bg-slate-800" />
        <div className="h-4 w-56 rounded bg-slate-800" />
      </div>

      <div className="mt-4">
        <div className="text-sm font-medium text-white">{title}</div>
        <div className="mt-1 text-sm text-slate-400">{description}</div>
      </div>
    </div>
  );
}
