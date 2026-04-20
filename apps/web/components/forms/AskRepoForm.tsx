"use client";

import { useRef, useState } from "react";
import type { AskRepoResponse } from "@/lib/types";

type Props = {
  repoId: string;
};

export function AskRepoForm({ repoId }: Props) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskRepoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestSeqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const currentQuestion = question.trim();
    if (!currentQuestion) return;

    requestSeqRef.current += 1;
    const requestSeq = requestSeqRef.current;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`/api/v1/repos/${encodeURIComponent(repoId)}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: currentQuestion,
          top_k: 6,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail =
          (payload && typeof payload.detail === "string" ? payload.detail : null) ||
          "Failed to ask repository";
        throw new Error(detail);
      }

      const payload = (await response.json()) as AskRepoResponse;
      if (requestSeq !== requestSeqRef.current) return;

      const cleanAnswer = (payload?.answer || "").trim();
      if (!cleanAnswer) {
        throw new Error("Received an empty answer for this query.");
      }

      setResult({
        ...payload,
        question: currentQuestion,
        answer: cleanAnswer,
      });
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      if (requestSeq !== requestSeqRef.current) return;
      setError(err instanceof Error ? err.message : "Failed to ask repository");
    } finally {
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
      }
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
          <div className="whitespace-pre-wrap text-sm text-slate-300 leading-relaxed">
            {result.answer}
          </div>

          <details
            className="group rounded-lg border border-slate-800 bg-slate-900 overflow-hidden"
            open={Array.isArray(result.citations) && result.citations.length > 0}
          >
            <summary className="cursor-pointer bg-slate-800/50 px-4 py-2 text-sm font-semibold text-slate-300 hover:bg-slate-800 focus:outline-none transition-colors">
              Sources & Citations
            </summary>
            <div className="space-y-2 p-4">
              {Array.isArray(result.citations) && result.citations.length > 0 ? (
                result.citations.map((c) => (
                  <div
                    key={c.chunk_id || Math.random()}
                    className="rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm"
                  >
                    <div className="font-medium text-slate-200">
                      {c.file_path || "unknown file"}
                    </div>
                    {c.start_line && (
                      <div className="text-slate-500 mt-1">
                        lines {c.start_line} - {c.end_line ?? "?"}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500 italic">No citations provided.</p>
              )}
            </div>
          </details>
        </div>
      ) : null}
    </div>
  );
}
