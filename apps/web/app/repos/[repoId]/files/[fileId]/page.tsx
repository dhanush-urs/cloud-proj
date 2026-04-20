import Link from "next/link";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { CodeBlockViewer } from "@/components/repo/CodeBlockViewer";
import { DataFileViewer } from "@/components/repo/DataFileViewer";
import { OfficePreviewPane } from "@/components/repo/OfficePreviewPane";
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
  const isPdf = file?.path && /\.pdf$/i.test(file.path);
  const isOffice = file?.path && /\.(pptx|ppt|docx|doc|xlsx|xls|odt|odp|ods)$/i.test(file.path);
  const isPpt = file?.path && /\.(pptx|ppt)$/i.test(file.path);

  // Build a browser-safe raw asset URL.
  // - If API base is configured for the browser, use it.
  // - Otherwise keep relative /api/v1/... paths so reverse proxies still work.
  const publicApiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
  const publicApiOrigin = publicApiBase.endsWith("/api/v1")
    ? publicApiBase.slice(0, -"/api/v1".length)
    : publicApiBase;

  let rawUrl = "";
  if (file?.raw_url) {
    if (/^https?:\/\//i.test(file.raw_url)) {
      rawUrl = file.raw_url;
    } else if (publicApiOrigin) {
      rawUrl = `${publicApiOrigin}${file.raw_url}`;
    } else {
      rawUrl = file.raw_url;
    }
  } else if (publicApiOrigin) {
    rawUrl = `${publicApiOrigin}/api/v1/repos/${repoId}/files/${fileId}/raw`;
  } else {
    rawUrl = `/api/v1/repos/${repoId}/files/${fileId}/raw`;
  }

  const shouldForceDownload =
    Boolean(isOffice) || Boolean(file?.is_binary && !isImage && !isPdf);
  const rawAssetLinkProps = shouldForceDownload
    ? { download: file?.path?.split("/").pop() || true }
    : { target: "_blank", rel: "noreferrer" as const };

  // previewUrl is always relative — works via the Next.js /api/v1 proxy rewrite.
  const previewUrl = `/api/v1/repos/${repoId}/files/${fileId}/preview`;

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
                <a
                  href={rawUrl}
                  {...rawAssetLinkProps}
                  className="inline-flex items-center rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-semibold text-slate-300 border border-slate-700 hover:bg-slate-700 transition-colors"
                >
                  Open Raw Asset ↗
                </a>
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
              ) : isPdf ? (
                <div className="h-[800px] w-full bg-slate-900/50 flex flex-col">
                  <div className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex justify-between items-center text-[10px] text-slate-500 font-mono">
                    <span>PDF PREVIEW</span>
                    <a 
                      href={rawUrl} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:underline"
                    >
                      Open in New Tab ↗
                    </a>
                  </div>
                  <div className="flex-1 relative">
                    <iframe
                      src={rawUrl}
                      className="h-full w-full border-0 absolute inset-0"
                      title="PDF Preview"
                    />
                    <div className="absolute inset-0 flex items-center justify-center -z-10 bg-slate-950 p-6 text-center">
                      <div className="max-w-xs">
                        <p className="text-sm text-slate-400 mb-2">Browser blocked the inline PDF preview.</p>
                        <a 
                          href={rawUrl} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-xs text-blue-500 hover:underline border border-blue-900/50 rounded px-2 py-1"
                        >
                          Click to View Raw Asset
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              ) : isOffice ? (
                isPpt ? (
                  <OfficePreviewPane
                    previewUrl={previewUrl}
                    rawUrl={rawUrl}
                    filename={file.path.split("/").pop() || ""}
                  />
                ) : (
                  <div className="px-6 py-12 text-center">
                    <div className="inline-flex flex-col items-center gap-4 rounded-2xl border border-slate-700 bg-slate-900/60 p-8 max-w-sm mx-auto">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-indigo-500/10 border border-indigo-500/20 text-2xl">
                        📄
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-slate-200 mb-1">
                          Office Document — No Inline Preview
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed">
                          {file.path.split(".").pop()?.toUpperCase()} files cannot be rendered
                          inline in the browser. Use the &ldquo;Open Raw Asset&rdquo; button
                          above to download and open locally.
                        </p>
                      </div>
                    </div>
                  </div>
                )
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
                  {file.is_binary || file.file_kind === "binary" ? (
                    <div className="space-y-4">
                      <p>This is a binary asset that cannot be rendered as text.</p>
                      <a
                        href={rawUrl}
                        download={file.path.split("/").pop() || true}
                        className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
                      >
                        Download / Open Raw Asset
                      </a>
                    </div>
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
