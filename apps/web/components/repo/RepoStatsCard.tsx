import { RepoStatusBadge } from "@/components/repo/RepoStatusBadge";
import type { Repository } from "@/lib/types";

type Props = {
  repo: Repository;
};

export function RepoStatsCard({ repo }: Props) {
  return (
    <div className="space-y-3 text-sm text-slate-300">
      <div>
        <span className="text-slate-400">Repository URL:</span>
        <div className="mt-1 break-all text-white">{repo.repo_url}</div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <span className="text-slate-400">Default Branch:</span>
          <div className="mt-1 text-white">{repo.default_branch}</div>
        </div>

        <div>
          <span className="text-slate-400">Status:</span>
          <div className="mt-2">
            <RepoStatusBadge status={repo.status} />
          </div>
        </div>

        <div>
          <span className="text-slate-400">Primary Language:</span>
          <div className="mt-1 text-white">
            {repo.primary_language || <span className="text-slate-500 italic">unknown</span>}
          </div>
        </div>

        <div>
          <span className="text-slate-400">Framework:</span>
          <div className="mt-1 text-white">
            {repo.framework || <span className="text-slate-500 italic">unknown</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
