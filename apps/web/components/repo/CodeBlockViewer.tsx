"use client";

import { useEffect, useRef } from "react";

type Props = {
  content: string;
  highlightLines?: number[];
};

export function CodeBlockViewer({ content, highlightLines = [] }: Props) {
  const lines = content.split("\n");
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const firstMatchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (highlightLines.length > 0 && firstMatchRef.current) {
      // Small delay to ensure layout is stable
      setTimeout(() => {
        firstMatchRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 100);
    }
  }, [highlightLines]);

  return (
    <div 
      ref={scrollContainerRef}
      className="overflow-auto rounded-xl border border-slate-800 bg-slate-950"
    >
      <div className="min-w-[900px]">
        {lines.map((line, index) => {
          const lineNo = index + 1;
          const isHighlighted = highlightLines.includes(lineNo);
          const isFirstHighlight = isHighlighted && (highlightLines[0] === lineNo);
          
          return (
            <div
              key={index}
              ref={isFirstHighlight ? firstMatchRef : null}
              className={`grid grid-cols-[72px_1fr] border-b border-slate-900 last:border-b-0 ${
                isHighlighted ? "bg-indigo-500/10" : ""
              }`}
            >
              <div 
                className={`select-none px-3 py-1 text-right text-xs border-r border-slate-900 ${
                  isHighlighted ? "bg-indigo-500/20 text-indigo-400 font-bold" : "bg-slate-900 text-slate-500"
                }`}
              >
                {lineNo}
              </div>
              <pre className={`overflow-x-auto px-4 py-1 text-xs leading-6 ${
                isHighlighted ? "text-indigo-200" : "text-slate-300"
              }`}>
                {line || " "}
              </pre>
            </div>
          );
        })}
      </div>
    </div>
  );
}

