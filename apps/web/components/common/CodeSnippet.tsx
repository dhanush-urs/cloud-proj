"use client";

import React from "react";

type Props = {
  content: string;
  startLine: number;
  highlightLines?: number[];
  className?: string;
};

export function CodeSnippet({ content, startLine, highlightLines = [], className = "" }: Props) {
  const lines = content.split("\n");
  
  return (
    <div className={`overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 font-mono text-[11px] leading-relaxed ${className}`}>
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line, i) => {
            const lineNum = startLine + i;
            const isHighlighted = highlightLines.includes(lineNum);
            
            return (
              <tr 
                key={i} 
                className={`${isHighlighted ? "bg-indigo-500/10" : "hover:bg-slate-900/40"}`}
              >
                <td className="w-10 select-none border-r border-slate-800 px-2 text-right text-slate-600">
                  {lineNum}
                </td>
                <td className={`whitespace-pre px-4 py-0.5 ${isHighlighted ? "text-indigo-200" : "text-slate-300"}`}>
                  {line || " "}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
