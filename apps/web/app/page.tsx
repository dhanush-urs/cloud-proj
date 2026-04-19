import Link from "next/link";
import { Card } from "@/components/common/Card";
import { PageHeader } from "@/components/common/PageHeader";
import { CreateRepoForm } from "@/components/forms/CreateRepoForm";

export default function HomePage() {
  try {
    return (
      <div className="space-y-8">
        <PageHeader
          title="RepoBrain"
          subtitle="AI-powered repository intelligence for search, onboarding, risk analysis, and change impact."
        />

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <h2 className="mb-3 text-2xl font-semibold text-white">
              Repository Intelligence Platform
            </h2>
            <p className="mb-5 text-sm leading-7 text-slate-300">
              RepoBrain ingests repositories, parses code structure, builds
              dependency context, runs semantic search, answers grounded
              engineering questions, detects hotspots, generates onboarding
              guides, and estimates PR blast radius.
            </p>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <div className="text-sm font-semibold text-white">
                  Semantic Search
                </div>
                <div className="mt-2 text-sm text-slate-400">
                  Query repository knowledge using embeddings and chunk retrieval.
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <div className="text-sm font-semibold text-white">Ask Repo</div>
                <div className="mt-2 text-sm text-slate-400">
                  Grounded repository Q&A powered by Gemini and retrieval context.
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <div className="text-sm font-semibold text-white">Hotspots</div>
                <div className="mt-2 text-sm text-slate-400">
                  Find risky files based on dependency centrality and structural
                  complexity.
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <div className="text-sm font-semibold text-white">PR Impact</div>
                <div className="mt-2 text-sm text-slate-400">
                  Estimate blast radius and review attention before merging.
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="mb-3 text-xl font-semibold text-white">Quick Start</h2>
            <p className="mb-4 text-sm text-slate-400">
              Add a GitHub repository, then parse and embed it from the repository
              dashboard.
            </p>
            <CreateRepoForm />
          </Card>
        </div>

        <Card>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white">
                Browse Repositories
              </h3>
              <p className="mt-1 text-sm text-slate-400">
                Open indexed repositories and use the full RepoBrain workflow.
              </p>
            </div>

            <Link
              href="/repos"
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Open Repositories
            </Link>
          </div>
        </Card>
      </div>
    );
  } catch (error) {
    console.error("Home page critical error:", error);
    return (
      <div className="p-8 text-center bg-slate-900 rounded-xl border border-red-500/30">
        <h1 className="text-2xl font-bold text-white mb-2">Startup Failure</h1>
        <p className="text-slate-400">The platform encountered an internal error. Please check the logs.</p>
      </div>
    );
  }
}
