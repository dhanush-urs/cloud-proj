import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { FileFilters } from "@/components/repo/FileFilters";
import { getRepositoryFiles } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RepoFilesPage({ params }: Props) {
  const { repoId } = await params;

  let data = null;

  try {
    data = await getRepositoryFiles(repoId, 300);
  } catch {
    data = null;
  }

  return (
    <div>
      <PageHeader
        title="File Explorer"
        subtitle="Search, filter, and inspect indexed repository files."
      />

      <RepoSubnav repoId={repoId} />

      {(() => {
        const hasData = data && Array.isArray(data.items);
        const isEmpty = !hasData || data.items.length === 0;
        const status = (data?.status || "unknown").toLowerCase();
        
        const isError = status === "failed";
        const inProgressStates = ["pending", "queued", "running", "syncing", "indexing", "parsing", "embedding"];
        const isInProgress = inProgressStates.includes(status);

        if (isEmpty) {
          if (isInProgress) {
            return (
              <EmptyState
                title="Indexing in Progress..."
                description="Repository file inventory is currently being built. Please check back in a few minutes."
              />
            );
          }
          if (isError) {
            return (
              <EmptyState
                title="Indexing Failed"
                description="The repository could not be indexed successfully. Files cannot be displayed."
              />
            );
          }
          return (
            <EmptyState
              title="No files available"
              description="Make sure the repository has been parsed before viewing files."
            />
          );
        }

        // We have files, but indexing might still be running
        return (
          <div className="space-y-6">
            {isInProgress && (
              <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200">
                <span className="font-semibold text-indigo-400">Indexing in progress:</span> File inventory and code analysis are actively running. Some files or metadata may not be visible yet.
              </div>
            )}
            <Card>
              <FileFilters repoId={repoId} files={data.items} />
            </Card>
          </div>
        );
      })()}
    </div>
  );
}
