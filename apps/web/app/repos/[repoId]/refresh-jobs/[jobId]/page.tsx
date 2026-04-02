import Link from "next/link";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { RefreshJobDetail } from "@/components/refresh/RefreshJobDetail";
import { getRefreshJob } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string; jobId: string }>;
};

export default async function RefreshJobDetailPage({ params }: Props) {
  const { repoId, jobId } = await params;

  let job = null;

  try {
    job = await getRefreshJob(jobId);
  } catch {
    job = null;
  }

  return (
    <div className="animate-in slide-in-from-bottom-2 duration-500">
      <PageHeader
        title="Refresh Job Detail"
        subtitle={`Inspecting operational event ID: ${jobId}`}
      />

      <RepoSubnav repoId={repoId} />

      <div className="mb-6">
        <Link
          href={`/repos/${repoId}/refresh-jobs`}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-white"
        >
          <span className="text-lg">←</span> Back to History
        </Link>
      </div>

      {!job ? (
        <EmptyState
          title="Refresh job not found"
          description="This job record might have been purged or the ID is incorrect."
        />
      ) : (
        <RefreshJobDetail initialJob={job} />
      )}
    </div>
  );
}
