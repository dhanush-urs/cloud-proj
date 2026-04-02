"use client";

type Props = {
  active: boolean;
};

export function PollingStatus({ active }: Props) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
      {active ? (
        <span className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
          </span>
          Live polling active (every 3s)
        </span>
      ) : (
        <span className="text-slate-500">All jobs complete — polling idle</span>
      )}
    </div>
  );
}
