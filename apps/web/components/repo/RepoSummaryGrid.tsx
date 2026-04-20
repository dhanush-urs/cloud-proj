import { Card } from "@/components/common/Card";
import type { Repository } from "@/lib/types";

type Props = {
  repo: Repository;
};

export function RepoSummaryGrid({ repo }: Props) {
  const sanitizeFramework = (val?: string | null) => {
    if (!val) return "unknown";
    return val.replace(/[{}[\]"']/g, "").split(",").map(s => s.trim()).filter(Boolean).join(", ");
  };

  const languages = repo.languages_used ?? [];

  const items = [
    {
      label: "Default Branch",
      value: repo.default_branch || <span className="text-slate-500 italic">none</span>,
    },
    {
      label: "Primary Language",
      value: repo.primary_language || <span className="text-slate-500 italic">unknown</span>,
    },
    {
      label: "Framework",
      value: sanitizeFramework(repo.framework),
    },
    {
      label: "Repository Status",
      value: repo.status || <span className="text-slate-500 italic">unknown</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <Card key={item.label}>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-400">
              {item.label}
            </div>
            <div className="mt-3 break-all overflow-hidden text-lg font-semibold text-white">
              {item.value}
            </div>
          </Card>
        ))}
      </div>

      {languages.length > 0 && (
        <Card>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-400 mb-3">
            Languages Used
          </div>
          <div className="flex flex-wrap gap-2">
            {languages.map((lang) => (
              <span
                key={lang}
                className="rounded-full bg-slate-800 border border-slate-700 px-3 py-1 text-sm text-slate-200 font-medium"
              >
                {lang}
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
