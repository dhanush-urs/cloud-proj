import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { RefreshJobsList } from "@/components/refresh/RefreshJobsList";
import { getRepositoryRefreshJobs } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RefreshJobsPage({ params }: Props) {
  const { repoId } = await params;

  let data = null;

  try {
    data = await getRepositoryRefreshJobs(repoId);
  } catch {
    data = null;
  }

  return (
    <div className="animate-in fade-in duration-500">
      <PageHeader
        title="Refresh Operations"
        subtitle="Track background synchronization, parsing, and re-indexing history."
      />

      <RepoSubnav repoId={repoId} />

      {!data ? (
        <EmptyState
          title="Refresh History Unavailable"
          description="We couldn't reach the backend to fetch refresh jobs. Ensure the API is healthy."
        />
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white tracking-tight">
              Recent Jobs
            </h2>
            <div className="px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs font-medium text-slate-400">
              {data.total} total events
            </div>
          </div>

          <RefreshJobsList repoId={repoId} initialJobs={data.items} />
        </div>
      )}
    </div>
  );
}
