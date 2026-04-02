"use client";

import { useState } from "react";
import { analyzeImpact } from "@/lib/api";
import type { PRImpactResponse } from "@/lib/types";

type Props = {
  repoId: string;
};

export function ImpactForm({ repoId }: Props) {
  const [changedFiles, setChangedFiles] = useState("src/flask/app.py");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PRImpactResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const files = changedFiles
        .split("\n")
        .map((f) => f.trim())
        .filter(Boolean);

      const response = await analyzeImpact(repoId, {
        changed_files: files,
        max_depth: 3,
      });

      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze impact");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={onSubmit} className="space-y-4">
        <textarea
          value={changedFiles}
          onChange={(e) => setChangedFiles(e.target.value)}
          rows={6}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none"
          placeholder={"src/flask/app.py\nsrc/flask/cli.py"}
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {loading ? "Analyzing..." : "Analyze PR Impact"}
        </button>
      </form>

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {result ? (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
          <div>
            <div className="text-sm text-slate-400">Overall Risk</div>
            <div className="text-xl font-bold text-white">
              {result.risk_level} ({result.total_impact_score})
            </div>
            <p className="mt-2 text-sm text-slate-300">{result.summary}</p>
          </div>

          <div>
            <h3 className="mb-2 text-lg font-semibold text-white">
              Impacted Files
            </h3>
            <div className="space-y-2">
              {result.impacted_files.map((file) => (
                <div
                  key={file.file_id}
                  className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm"
                >
                  <div className="font-medium text-slate-200">{file.path}</div>
                  <div className="text-slate-400">
                    depth={file.depth} | risk={file.risk_score} | impact=
                    {file.impact_score}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-lg font-semibold text-white">
              Reviewer Hints
            </h3>
            <div className="space-y-2">
              {result.reviewer_suggestions.map((r, idx) => (
                <div
                  key={`${r.reviewer_hint}-${idx}`}
                  className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm"
                >
                  <div className="font-medium text-slate-200">
                    {r.reviewer_hint}
                  </div>
                  <div className="text-slate-400">{r.reason}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
