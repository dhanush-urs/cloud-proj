import Link from "next/link";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { CodeBlockViewer } from "@/components/repo/CodeBlockViewer";
import { DataFileViewer } from "@/components/repo/DataFileViewer";
import { getRepositoryFileDetail } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string; fileId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function FileDetailPage({ params, searchParams }: Props) {
  const { repoId, fileId } = await params;
  const sParams = await searchParams;

  // Guard: ensure fileId is a valid non-empty, non-null string before fetching
  const isValidFileId =
    fileId &&
    fileId !== "null" &&
    fileId !== "undefined" &&
    fileId.length > 4;

  // Safely parse ?line=N — must be a positive integer
  const highlightLineStr = sParams.line as string | undefined;
  const parsedLine = highlightLineStr ? parseInt(highlightLineStr, 10) : NaN;
  const highlightLines =
    !isNaN(parsedLine) && parsedLine > 0 ? [parsedLine] : [];

  let file = null;
  let fetchError: string | null = null;

  if (!isValidFileId) {
    fetchError = `Invalid file ID: "${fileId}"`;
  } else {
    try {
      file = await getRepositoryFileDetail(repoId, fileId);
      if (!file) {
        fetchError = `File with ID "${fileId}" was not found in the repository.`;
      }
    } catch (err) {
      fetchError =
        err instanceof Error
          ? `Failed to load file: ${err.message}`
          : "An unexpected error occurred while loading the file.";
    }
  }

  const isImage = file?.path && /\.(jpg|jpeg|png|gif|webp|svg)$/i.test(file.path);
  const rawUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/repos/${repoId}/files/${fileId}/raw`;


  return (
    <div>
      <PageHeader
        title="File Detail"
        subtitle={file?.path || (isValidFileId ? "Loading file..." : "Invalid file")}
      />

      <RepoSubnav repoId={repoId} />

      {fetchError ? (
        /* Error state — never a blank screen */
        <div className="mt-6 rounded-2xl border border-rose-500/20 bg-rose-500/5 p-8">
          <div className="flex items-start gap-4">
            <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-rose-500/10 text-rose-400">
              ✕
            </div>
            <div>
              <h2 className="text-base font-semibold text-rose-300">
                File could not be loaded
              </h2>
              <p className="mt-1 text-sm text-rose-400/80">{fetchError}</p>
              <div className="mt-4 flex gap-3">
                <Link
                  href={`/repos/${repoId}/files`}
                  className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
                >
                  ← Back to File Explorer
                </Link>
                <Link
                  href={`/repos/${repoId}/search`}
                  className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
                >
                  Search Again
                </Link>
              </div>
            </div>
          </div>
        </div>
      ) : !file ? (
        <EmptyState
          title="File not found"
          description="This file could not be loaded. The file may have been removed or not yet indexed."
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
                  {highlightLines.length > 0 && (
                    <span className="ml-3 rounded-full bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-400 border border-indigo-500/20">
                      Jump to line {highlightLines[0]}
                    </span>
                  )}
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
                  href={`/repos/${repoId}/files`}
                  className="rounded-md border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-800"
                >
                  ← File Explorer
                </Link>
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

            <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
              {isImage ? (
                <div className="flex flex-col items-center justify-center p-10 bg-slate-900/50">
                  <img
                    src={rawUrl}
                    alt={file.path}
                    className="max-w-full h-auto shadow-2xl rounded-sm border border-slate-800 bg-[url('/checkerboard.png')] bg-repeat"
                  />
                  <div className="mt-4 text-xs text-slate-500 font-mono">
                    Binary Image Asset
                  </div>
                </div>
              ) : file.content ? (
                <div className="p-4">
                  <DataFileViewer
                    content={file.content}
                    path={file.path}
                    highlightLines={highlightLines}
                  />
                </div>
              ) : (
                <div className="px-6 py-10 text-center text-sm text-slate-500">
                  <div className="mb-2 text-slate-400 font-medium">No text content available.</div>
                  {file.file_kind === "binary" ? (
                    <div>This is a binary file. Use the "Open Raw" button to view or download it.</div>
                  ) : (
                    <div>The file content has not been indexed yet.</div>
                  )}
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
