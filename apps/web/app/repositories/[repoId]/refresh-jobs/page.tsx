import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { RefreshJobsList } from "@/components/refresh/RefreshJobsList";
import { RepoStatusPanel } from "@/components/repo/RepoStatusPanel";
import { getRepository, getRepositoryRefreshJobs } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RefreshJobsPage({ params }: Props) {
  const { repoId } = await params;

  // Parallel fetch for repository details and refresh history
  const [repo, jobsData] = await Promise.all([
    getRepository(repoId).catch(() => null),
    getRepositoryRefreshJobs(repoId).catch(() => ({ items: [], total: 0 })),
  ]);

  if (!repo) {
    return (
      <div className="animate-in fade-in duration-500">
        <PageHeader
          title="Refresh History Error"
          subtitle="We were unable to locate this repository profile."
        />
        <div className="mt-8 p-12 text-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/40">
           <h3 className="text-white font-semibold">Repository Not Found</h3>
           <p className="text-slate-500 text-sm mt-2">The repository ID may be invalid or it may have been deleted.</p>
        </div>
      </div>
    );
  }

  const hasJobs = jobsData && jobsData.items && jobsData.items.length > 0;

  return (
    <div className="animate-in fade-in duration-500 pb-20">
      <PageHeader
        title="Refresh Operations"
        subtitle="Track background synchronization, parsing, and re-indexing history."
      />

      <RepoSubnav repoId={repoId} />

      <div className="space-y-10 mt-8">
        {/* Always show the status panel for visibility into current state */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white tracking-tight px-1">
              Live Status
            </h2>
          </div>
          <RepoStatusPanel repo={repo} />
        </section>

        {/* Show history if available, otherwise show a cleaner fallback */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white tracking-tight px-1">
              Recent Activity
            </h2>
            {hasJobs && (
              <div className="px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-[10px] font-black uppercase tracking-widest text-slate-500">
                {jobsData.total} events logged
              </div>
            )}
          </div>

          {!hasJobs ? (
            <div className="p-12 text-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 backdrop-blur-sm">
                <p className="text-slate-400 text-sm font-medium">No Refresh History</p>
                <p className="text-slate-500 text-[13px] mt-1 max-w-sm mx-auto">
                    No background synchronization events have been logged yet. Refresh operations will appear here once triggered.
                </p>
            </div>
          ) : (
            <RefreshJobsList repoId={repoId} initialJobs={jobsData.items} />
          )}
        </section>
      </div>
    </div>
  );
}
