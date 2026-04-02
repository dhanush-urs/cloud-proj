import { Card } from "@/components/common/Card";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { SearchForm } from "@/components/repo/SearchForm";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RepoSearchPage({ params }: Props) {
  const { repoId } = await params;

  return (
    <div>
      <PageHeader
        title="Semantic Search"
        subtitle="Search repository knowledge using embeddings."
      />

      <RepoSubnav repoId={repoId} />

      <Card>
        <SearchForm repoId={repoId} />
      </Card>
    </div>
  );
}
