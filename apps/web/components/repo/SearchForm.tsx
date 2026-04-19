"use client";

import Link from "next/link";
import { useState } from "react";
import { CodeSnippet } from "@/components/common/CodeSnippet";
import { semanticSearch } from "@/lib/api";
import type { SemanticSearchResponse } from "@/lib/types";

type Props = {
  repoId: string;
};

export function SearchForm({ repoId }: Props) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SemanticSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const response = await semanticSearch(repoId, {
        query,
        top_k: 8,
      });
      setResult(response);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to search repository"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit} className="relative">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit(e as any);
            }
          }}
          rows={3}
          className="w-full rounded-2xl border border-slate-800 bg-slate-950/50 p-4 text-white outline-none transition-all placeholder:text-slate-600 focus:border-blue-500/50 focus:bg-slate-950 focus:ring-4 focus:ring-blue-500/10"
          placeholder="Search codebase (e.g. 'find all auth routes' or 'import pandas')"
        />
        <div className="absolute bottom-3 right-3 flex items-center gap-3">
           <div className="text-[10px] text-slate-500 font-mono">
             Shift + Enter for new line
           </div>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-500 hover:shadow-blue-500/40 disabled:opacity-30 disabled:shadow-none"
          >
            {loading ? (
              <>
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                Searching...
              </>
            ) : (
              "Search"
            )}
          </button>
        </div>
      </form>

      {error ? (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">
              Results ({result.total})
            </h3>
            {result.items.length > 0 && (
              <div className="text-[10px] text-slate-600 font-mono">
                Hybrid retrieval active
              </div>
            )}
          </div>

          <div className="grid gap-4">
            {Array.isArray(result.items) && result.items.length > 0 ? (
              result.items.map((item) => {
                const matchedLines = Array.isArray(item.matched_lines) ? item.matched_lines : [];
                const firstMatchLine = matchedLines.length > 0 ? matchedLines[0] : null;
                const isExact = item.match_type === "exact" || (item.score > 0.95);

                // Guard: only build the file link if file_id is a valid non-null UUID
                const hasFileId = item.file_id && item.file_id !== "null";
                const fileHref = hasFileId
                  ? `/repos/${repoId}/files/${item.file_id}${firstMatchLine ? `?line=${firstMatchLine}` : ""}`
                  : null;

                return (
                  <div
                    key={item.chunk_id}
                    className={`group relative overflow-hidden rounded-2xl border transition-all duration-300 ${
                      isExact
                        ? "border-blue-500/30 bg-blue-500/[0.02] hover:border-blue-500/50"
                        : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-inherit px-4 py-3 bg-inherit">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-2">
                          <code className="text-sm font-semibold text-slate-200">
                            {item.file_path || "unknown file"}
                          </code>
                          {isExact && (
                            <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-tighter text-blue-400 border border-blue-500/20">
                              Best Match
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono uppercase tracking-widest">
                          <span>{item.chunk_type || "code"}</span>
                          <span>•</span>
                          <span>Relevance {(item.score * 100).toFixed(1)}%</span>
                          {firstMatchLine && (
                            <>
                              <span>•</span>
                              <span className="text-indigo-400">Line {firstMatchLine}</span>
                            </>
                          )}
                        </div>
                      </div>

                      {fileHref ? (
                        <Link
                          href={fileHref}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-medium text-slate-300 transition-all hover:bg-slate-900 group-hover:border-slate-600"
                        >
                          Open File{" "}
                          {firstMatchLine && (
                            <span className="text-blue-400">L{firstMatchLine}</span>
                          )}
                        </Link>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900/30 px-3 py-1.5 text-xs font-medium text-slate-600 cursor-not-allowed">
                          No file link
                        </span>
                      )}
                    </div>

                    <div className="p-1">
                      <CodeSnippet
                        content={item.snippet || ""}
                        startLine={typeof item.start_line === "number" ? item.start_line : 1}
                        highlightLines={matchedLines}
                        className="border-none bg-transparent"
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 py-12 text-center">
                <div className="mb-2 text-slate-600">No matching results found</div>
                <div className="text-xs text-slate-700 max-w-xs">
                  Try adjusting your query or ensure the repository is fully indexed.
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
