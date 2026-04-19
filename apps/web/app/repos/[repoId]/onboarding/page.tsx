import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { MarkdownView } from "@/components/repo/MarkdownView";
import { generateOnboarding, getOnboarding } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string }>;
};

export default async function RepoOnboardingPage({ params }: Props) {
  const { repoId } = await params;

  let doc = null;

  try {
    doc = await getOnboarding(repoId);
  } catch {
    try {
      await generateOnboarding(repoId);
      doc = await getOnboarding(repoId);
    } catch {
      doc = null;
    }
  }

  return (
    <div>
      <PageHeader
        title="Onboarding Guide"
        subtitle="AI-generated onboarding document for new engineers."
      />

      <RepoSubnav repoId={repoId} />

      {!doc ? (
        <EmptyState
          title="No onboarding document available"
          description="Generate onboarding from the backend API or ensure the repo has been parsed and embedded."
        />
      ) : (
        <Card>
          <div className="mb-6 flex flex-wrap gap-2 text-xs text-slate-400">
            <span>version: {doc.version || "1.0.0"}</span>
            <span>mode: {doc.generation_mode || "standard"}</span>
            {doc.llm_model ? <span>model: {doc.llm_model}</span> : null}
          </div>

          <MarkdownView content={doc.content_markdown || "No content generated."} />
        </Card>
      )}
    </div>
  );
}
