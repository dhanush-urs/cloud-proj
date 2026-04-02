import { Card } from "@/components/common/Card";
import { PageHeader } from "@/components/common/PageHeader";
import { ImpactForm } from "@/components/forms/ImpactForm";
import { RepoSubnav } from "@/components/layout/RepoSubnav";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RepoImpactPage({ params }: Props) {
  const { repoId } = await params;

  return (
    <div>
      <PageHeader
        title="PR Impact Analyzer"
        subtitle="Estimate blast radius before you merge."
      />

      <RepoSubnav repoId={repoId} />

      <Card>
        <ImpactForm repoId={repoId} />
      </Card>
    </div>
  );
}
