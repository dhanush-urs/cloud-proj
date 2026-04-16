"use client";

import { useState } from "react";
import { askRepo } from "@/lib/api";
import type { AskRepoResponse, RenameAnalysis } from "@/lib/types";

type Props = {
  repoId: string;
};

export function AskRepoForm({ repoId }: Props) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskRepoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function cleanAnswer(text: string) {
    if (!text) return "";
    return text
      .replace(/^[=\-]{3,}$/gm, "") // Remove separator lines like ==== or ----
      .replace(/#{1,6}\s/g, "") // Remove all markdown headers
      .replace(/\*\*/g, "") // bold
      .replace(/__/g, "") // italic/bold
      .replace(/`/g, "") // inline code
      .trim();
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await askRepo(repoId, {
        question,
        top_k: 5,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ask repository");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={onSubmit} className="space-y-4">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit(e as any);
            }
          }}
          rows={4}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none"
          placeholder="Ask a question about the repository..."
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {loading ? "Thinking..." : "Ask Repo"}
        </button>
      </form>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {result ? (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
          <div className="flex flex-wrap gap-2">
            {result.confidence ? (
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider ${
                result.confidence === 'high' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' :
                result.confidence === 'medium' ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400' :
                'border-rose-500/30 bg-rose-500/10 text-rose-400'
              }`}>
                {result.confidence === 'high' ? 'High Confidence' : 
                 result.confidence === 'medium' ? 'Medium Confidence' : 
                 'Low Confidence'}
              </span>
            ) : null}
            {result.resolved_file ? (
              <span className="rounded-full border border-blue-800 bg-blue-950 px-2 py-1 text-xs text-blue-300">
                {result.resolved_file}
                {result.resolved_line_number ? `:${result.resolved_line_number}` : ""}
              </span>
            ) : null}
          </div>

          {/* Rename Impact Card — shown when backend resolves a rename analysis */}
          {result.rename_analysis ? (
            <RenameImpactCard ra={result.rename_analysis} />
          ) : null}

          <div className="pt-2">
            <h3 className="mb-3 text-lg font-semibold text-slate-100">Analysis</h3>
            <div className="text-sm text-slate-300 leading-relaxed prose prose-invert max-w-none selection:bg-blue-500/30">
              {cleanAnswer(result.answer)}
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-lg font-semibold text-white">Citations</h3>
            <div className="space-y-2">
              {result.citations.map((c) => (
                <div
                  key={c.chunk_id}
                  className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm"
                >
                  <div className="font-medium text-slate-200">
                    {c.file_path || "unknown file"}
                  </div>
                  <div className="text-slate-400">
                    lines {c.start_line ?? "?"} - {c.end_line ?? "?"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RenameImpactCard({ ra }: { ra: RenameAnalysis }) {
  const refs = ra.same_file_references ?? [];
  return (
    <div className="rounded-lg border border-amber-700/40 bg-amber-950/20 p-4 text-sm space-y-3">
      <div className="font-semibold text-amber-300">
        Rename Impact: &apos;{ra.symbol_name}&apos; → &apos;{ra.new_name}&apos;
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
        <span>Resolved File</span>
        <span className="text-slate-200 truncate">{(ra as any).file_path ?? "see answer"}</span>
        <span>Declaration Line</span>
        <span className="text-slate-200">{ra.declaration_line}</span>
        <span>Language</span>
        <span className="text-slate-200">{ra.language}</span>
      </div>
      {refs.length > 0 ? (
        <div className="space-y-1">
          <div className="text-rose-400 font-medium">
            Declaration-only rename BREAKS — {refs.length} reference{refs.length !== 1 ? "s" : ""} still use &apos;{ra.symbol_name}&apos;:
          </div>
          <div className="rounded bg-slate-950 p-2 space-y-0.5 max-h-40 overflow-y-auto">
            {refs.map((r) => (
              <div key={r.line_no} className="text-xs text-slate-300 font-mono">
                <span className="text-slate-500 mr-2">line {r.line_no}</span>
                {r.line_text}
              </div>
            ))}
          </div>
          <div className="text-xs text-slate-400">
            Error if partial: <span className="text-rose-300">{ra.error_if_partial}</span>
          </div>
        </div>
      ) : (
        <div className="text-emerald-400 text-xs">
          No same-file references found after declaration — rename appears safe in this file.
        </div>
      )}
      {ra.full_rename_safe ? (
        <div className="text-emerald-400 text-xs">
          Full consistent rename (all references updated) is safe — no behavioral change.
        </div>
      ) : null}
    </div>
  );
}
