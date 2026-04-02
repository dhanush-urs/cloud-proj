import Link from "next/link";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { CodeBlockViewer } from "@/components/repo/CodeBlockViewer";
import { getRepositoryFileDetail } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string; fileId: string }>;
};

export default async function FileDetailPage({ params }: Props) {
  const { repoId, fileId } = await params;

  let file = null;

  try {
    file = await getRepositoryFileDetail(repoId, fileId);
  } catch {
    file = null;
  }

  return (
    <div>
      <PageHeader title="File Detail" subtitle={file?.path || "Indexed file"} />

      <RepoSubnav repoId={repoId} />

      {!file ? (
        <EmptyState
          title="File not found"
          description="This file could not be loaded. Ensure the backend file detail endpoint is implemented."
        />
      ) : (
        <div className="space-y-4">
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="break-all text-lg font-semibold text-white">
                  {file.path}
                </div>
                <div className="mt-2 text-sm text-slate-400">
                  {file.language || "unknown"} • {file.file_kind}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge label={file.parse_status || "unknown"} />
                {file.is_generated ? (
                  <Badge label="generated" tone="yellow" />
                ) : null}
                {file.is_vendor ? <Badge label="vendor" tone="blue" /> : null}
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-3 text-sm text-slate-300">
              <div>Lines: {file.line_count ?? "-"}</div>
              <div>Language: {file.language || "unknown"}</div>
              <div>Kind: {file.file_kind}</div>
            </div>
          </Card>

          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-white">
                Content Preview
              </h2>
              <div className="flex gap-2">
                <Link
                  href={`/repos/${repoId}/search`}
                  className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
                >
                  Semantic Search
                </Link>
                <Link
                  href={`/repos/${repoId}/chat`}
                  className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
                >
                  Ask Repo
                </Link>
              </div>
            </div>

            <CodeBlockViewer
              content={file.content || "No content available for this file."}
            />
          </Card>
        </div>
      )}
    </div>
  );
}
