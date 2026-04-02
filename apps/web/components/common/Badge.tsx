type Props = {
  label: string;
  tone?: "default" | "green" | "yellow" | "red" | "blue";
};

const toneMap: Record<NonNullable<Props["tone"]>, string> = {
  default: "bg-slate-800 text-slate-200 border-slate-700",
  green: "bg-emerald-950 text-emerald-300 border-emerald-800",
  yellow: "bg-amber-950 text-amber-300 border-amber-800",
  red: "bg-rose-950 text-rose-300 border-rose-800",
  blue: "bg-blue-950 text-blue-300 border-blue-800",
};

export function Badge({ label, tone = "default" }: Props) {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${toneMap[tone]}`}
    >
      {label}
    </span>
  );
}
