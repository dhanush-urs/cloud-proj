import { Card } from "@/components/common/Card";
import { PageHeader } from "@/components/common/PageHeader";
import { AskRepoForm } from "@/components/forms/AskRepoForm";
import { RepoSubnav } from "@/components/layout/RepoSubnav";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RepoChatPage({ params }: Props) {
  const { repoId } = await params;

  return (
    <div>
      <PageHeader
        title="Ask Repo"
        subtitle="Ask grounded questions about the indexed repository."
      />

      <RepoSubnav repoId={repoId} />

      <Card>
        <AskRepoForm repoId={repoId} />
      </Card>
    </div>
  );
}
