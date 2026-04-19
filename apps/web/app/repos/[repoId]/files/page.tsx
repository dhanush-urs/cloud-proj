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

      {!data || !Array.isArray(data.items) || data.items.length === 0 ? (
        <EmptyState
          title="No files available"
          description="Make sure the repository has been parsed before viewing files."
        />
      ) : (
        <Card>
          <FileFilters repoId={repoId} files={data.items} />
        </Card>
      )}
    </div>
  );
}
