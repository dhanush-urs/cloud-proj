"use client";

import Link from "next/link";
import { useState } from "react";
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
    <div className="space-y-5">
      <form onSubmit={onSubmit} className="space-y-4">
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
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none"
          placeholder="Search the codebase semantically..."
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {loading ? "Searching..." : "Semantic Search"}
        </button>
      </form>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {result ? (
        <div className="space-y-3">
          <div className="text-sm text-slate-400">
            Found {result.total} result(s)
          </div>

          {result.items.map((item) => (
            <div
              key={item.chunk_id}
              className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-medium text-white">
                    {item.file_path || "unknown file"}
                  </div>
                  <div className="text-xs text-slate-400">
                    score={item.score.toFixed(4)} • {item.chunk_type} • lines{" "}
                    {item.start_line ?? "?"}-{item.end_line ?? "?"}
                  </div>
                </div>

                {item.file_id ? (
                  <Link
                    href={`/repos/${repoId}/files/${item.file_id}`}
                    className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                  >
                    Open File
                  </Link>
                ) : null}
              </div>

              <pre className="mt-3 rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
                {item.snippet}
              </pre>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
