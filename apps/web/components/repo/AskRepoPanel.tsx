"use client";

import { AskRepoResponse } from "@/lib/types";

type Props = {
  result: AskRepoResponse;
};

function cleanMarkdown(text: string) {
  if (!text) return "";
  return text
    .replace(/\*\*/g, "") // bold
    .replace(/__/g, "") // italic/bold
    .replace(/`/g, "") // inline code
    .replace(/^-\s+/gm, "• ") // bullets
    .trim();
}

export function AskRepoPanel({ result }: Props) {
  const isImpact = result.query_type === "line_impact" || result.query_type === "line_change_impact";
  const isRepoSummary = result.query_type === "repo_summary";
  const isFileSummary = result.query_type === "file_summary";

  // Parse structured sections from Gemini markdown
  const sections: { title: string; body: string }[] = [];
  const rawAnswer = result.answer || "";
  
  if (isImpact || isFileSummary) {
    const parts = rawAnswer.split(/(?:^|\n)###\s+/);
    for (const part of parts) {
      if (!part.trim()) continue;
      const lines = part.split("\n");
      const title = lines[0].trim();
      const body = cleanMarkdown(lines.slice(1).join("\n"));
      
      // Skip sections already rendered gracefully by native fields 
      // or that are useless prompt artifacts
      const skipTitles = [
        "Query Type", "Exact Repo Lookup", "Resolved File", 
        "Resolved Line Number", "Matched Line", "Match Type", 
        "Extracted Symbols", "Evidence Citations", "Grounded Confidence", "Risk Level"
      ];
      
      if (!skipTitles.some(t => title.includes(t)) && body) {
        sections.push({ title, body });
      }
    }
  } else {
    // Basic clean for generic queries, strip headers entirely
    sections.push({ 
      title: "Analysis", 
      body: cleanMarkdown(rawAnswer.replace(/(?:^|\n)###\s+.*$/gm, '')) 
    });
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Meta Header */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-300">
          Intent: {result.query_type || "General Search"}
        </span>
        <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-slate-300">
          Mode: {result.mode}
        </span>
        {result.mode === "gemini_synthesized" && (
          <span className="flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-blue-400">
             <span className="relative flex h-2 w-2">
               <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
               <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
             </span>
             Gemini Engine
          </span>
        )}
        {result.mode === "deterministic_fallback" && (
          <span className="flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-amber-500">
             <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
             </svg>
             Deterministic Fallback
          </span>
        )}
        {result.confidence && (
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider ${
            result.confidence === 'high' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400' :
            result.confidence === 'medium' ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400' :
            'border-rose-500/30 bg-rose-500/10 text-rose-400'
          }`}>
            Confidence: {result.confidence}
          </span>
        )}
      </div>

      {/* Target Resolution Block (for Line/File Impact) */}
      {(isImpact || isFileSummary) && result.resolved_file && (
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">Target Resolution</h4>
          <div className="font-mono text-sm text-slate-200">
            <div>
              <span className="text-slate-400">File: </span> 
              <span className="text-indigo-300">{result.resolved_file}</span>
            </div>
            {result.resolved_line_number && (
              <div className="mt-1">
                <span className="text-slate-400">Line {result.resolved_line_number}: </span>
                <span className="bg-slate-900 px-1 py-0.5 rounded text-indigo-200">{result.matched_line?.trim() || "..."}</span>
              </div>
            )}
            {result.enclosing_scope && (
              <div className="mt-1">
                <span className="text-slate-400">Scope: </span>
                <span className="text-slate-300">{result.enclosing_scope}</span>
                {result.line_type && <span className="ml-2 text-xs text-slate-500">({result.line_type})</span>}
              </div>
            )}
            {result.snippet_found === false && (
              <div className="mt-2 text-rose-400 text-xs flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                Failed to resolve exact repository location. Falling back to semantic search / general explanation.
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Answer Column */}
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 overflow-hidden shadow-xl">
            <div className="border-b border-slate-800 bg-slate-900 px-4 py-3">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                Intelligence Synthesis
              </h3>
            </div>
            <div className="p-5 flex flex-col gap-5">
              {sections.length > 0 ? (
                sections.map((sec, idx) => (
                  <div key={idx} className="space-y-1">
                    {sec.title !== "Analysis" && (
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                        {sec.title}
                      </h4>
                    )}
                    <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                      {sec.body}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                  {cleanMarkdown(rawAnswer)}
                </div>
              )}
            </div>

            {/* Precision Analysis Supplement */}
            {result.rename_analysis && (
              <div className="border-t border-slate-800 bg-indigo-950/10 p-5 mt-4 group">
                <div className="flex items-center gap-2 mb-4">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                  </span>
                  <h4 className="text-[11px] font-bold uppercase tracking-[0.15em] text-indigo-400/90 group-hover:text-indigo-300 transition-colors">Symbolic Precision Analysis</h4>
                </div>
                
                {result.operation === "rename" && (
                  <div className="space-y-5">
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700/50 text-xs font-mono">
                         <span className="text-slate-500 line-through">{result.rename_analysis.symbol_name}</span>
                         <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" /></svg>
                         <span className="text-indigo-300 font-bold">{result.rename_analysis.new_name}</span>
                      </div>
                      
                      {result.rename_analysis.full_rename_safe ? (
                        <span className="flex items-center gap-1.5 text-[10px] bg-emerald-500/10 text-emerald-400 px-3 py-1 rounded-full border border-emerald-500/20 font-bold uppercase tracking-wider">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                          Safe Refactor
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5 text-[10px] bg-rose-500/10 text-rose-400 px-3 py-1 rounded-full border border-rose-500/20 font-bold uppercase tracking-wider">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                          Breaks Detected
                        </span>
                      )}
                    </div>

                    {result.rename_analysis.same_file_references && result.rename_analysis.same_file_references.length > 0 && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest px-1">Unresolved References</p>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono italic">same-file resolution</span>
                        </div>
                        <div className="grid gap-2.5">
                          {result.rename_analysis.same_file_references.slice(0, 5).map((usage, ux) => (
                            <div key={ux} className="flex flex-col rounded-lg border border-slate-700/50 bg-slate-900/50 p-3 hover:border-rose-500/30 transition-all duration-300">
                              <div className="flex items-center justify-between gap-4 overflow-hidden">
                                <code className="text-[11px] text-indigo-200/90 truncate font-mono bg-indigo-950/30 px-1 rounded">{usage.line_text}</code>
                                <span className="text-[10px] font-bold text-slate-500 shrink-0 tabular-nums">LINE {usage.line_no}</span>
                              </div>
                              <div className="flex items-center gap-1.5 mt-2">
                                <div className="h-1 w-1 rounded-full bg-rose-500" />
                                <span className="text-[10px] text-rose-400/80 font-medium">Unresolved reference</span>
                              </div>
                            </div>
                          ))}
                          {result.rename_analysis.same_file_references.length > 5 && (
                            <p className="text-[10px] text-slate-600 italic pl-1">...and {result.rename_analysis.same_file_references.length - 5} more references</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {result.operation === "delete" && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Classification:</span>
                      <span className="text-[10px] font-bold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">{result.deletion_type || "Generic Deletion"}</span>
                    </div>
                    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 text-[13px] text-amber-200/70 leading-relaxed italic shadow-inner">
                      Performing heuristic dependency trace for potential orphaned references...
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar Data Column */}
        <div className="space-y-4">
          {/* Notes */}
          {result.notes && result.notes.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Resolution Steps</h4>
              <ul className="space-y-2">
                {result.notes.map((note, idx) => (
                  <li key={idx} className="text-xs text-slate-400 flex items-start gap-2">
                    <span className="text-slate-600 mt-0.5">•</span>
                    {note}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Citations */}
          {result.citations && result.citations.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Primary Evidence</h4>
              <div className="space-y-2">
                {result.citations.map((c, idx) => (
                  <div key={idx} className="rounded border border-slate-800/60 bg-slate-950/50 p-2">
                    <div className="text-xs font-medium text-slate-300 break-all">
                      {c.file_path || "unknown"}
                    </div>
                    {(c.start_line != null || c.match_type) && (
                      <div className="mt-1 flex items-center gap-2">
                        {c.start_line != null && (
                          <span className="text-[10px] text-slate-500 font-mono">
                            L{c.start_line}{c.end_line && c.end_line !== c.start_line ? `-${c.end_line}` : ""}
                          </span>
                        )}
                        {c.match_type && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                            {c.match_type}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
