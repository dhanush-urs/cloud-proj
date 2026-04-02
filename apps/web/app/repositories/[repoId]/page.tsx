import Link from "next/link";
import { Card } from "@/components/common/Card";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { RepoActions } from "@/components/repo/RepoActions";
import { RepoStatsCard } from "@/components/repo/RepoStatsCard";
import { RepoSummaryGrid } from "@/components/repo/RepoSummaryGrid";
import { getRepository } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string }>;
};

export const dynamic = "force-dynamic";

export default async function RepoOverviewPage({ params }: Props) {
  const { repoId } = await params;
  const repo = await getRepository(repoId);

  return (
    <div className="animate-in fade-in duration-700">
      <PageHeader title="Repository Overview" subtitle={repo.repo_url} />

      <RepoSubnav repoId={repoId} />

      <RepoSummaryGrid repo={repo} />

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold text-white">
            Repository Details
          </h2>
          <RepoStatsCard repo={repo} />
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="mb-4 text-lg font-semibold text-white">
              Repository Actions
            </h2>
            <RepoActions repoId={repoId} initialStatus={repo.status} />

            <div className="mt-6 pt-6 border-t border-slate-800">
              <Link
                href={`/repositories/${repoId}/refresh-jobs`}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5 text-sm font-semibold text-indigo-400 transition-all hover:bg-indigo-500/20 hover:border-indigo-500/50"
              >
                <span>View Refresh Logs</span>
                <span className="text-lg">→</span>
              </Link>
            </div>
          </Card>

          <Card>
            <h2 className="mb-3 text-lg font-semibold text-white">
              Operational Surface
            </h2>
            <ul className="space-y-3 text-sm text-slate-400">
              <li className="flex items-start gap-3">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0"></span>
                <span>Webhook-triggered incremental re-parsing.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0"></span>
                <span>Branch-aware PR analysis and impact scoring.</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0"></span>
                <span>Selective symbol and dependency edge rebuilding.</span>
              </li>
            </ul>
          </Card>
        </div>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-lg font-semibold text-white">
            Suggested Workflow
          </h2>
          <ol className="list-decimal space-y-3 pl-5 text-sm text-slate-300">
            <li>
              Parse the repository to extract files, symbols, and dependencies.
            </li>
            <li>Embed the repository for semantic search and Ask Repo.</li>
            <li>Review hotspots to understand risky files.</li>
            <li>Generate onboarding docs for new contributors.</li>
            <li>Run PR impact analysis before major changes.</li>
            <li>Monitor refresh logs for real-time operation status.</li>
          </ol>
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-semibold text-white">
            Feature Surface
          </h2>
          <ul className="list-disc space-y-3 pl-5 text-sm text-slate-300">
            <li>File Explorer for indexed file browsing</li>
            <li>Semantic Search over embedded chunks</li>
            <li>Ask Repo for grounded Q&A with citations</li>
            <li>Risk Hotspots for high-attention files</li>
            <li>Onboarding Guide generation from AST context</li>
            <li>PR Impact blast-radius estimation engine</li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
