"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { FileRecord } from "@/lib/types";

type Props = {
  repoId: string;
  files: FileRecord[];
};

export function FileFilters({ repoId, files }: Props) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");

  const kinds = useMemo(() => {
    const values = Array.from(new Set(files.map((f) => f.file_kind))).sort();
    return ["all", ...values];
  }, [files]);

  const filtered = useMemo(() => {
    return files.filter((file) => {
      const matchesQuery =
        !query ||
        file.path.toLowerCase().includes(query.toLowerCase()) ||
        (file.language || "").toLowerCase().includes(query.toLowerCase());

      const matchesKind = kind === "all" || file.file_kind === kind;

      return matchesQuery && matchesKind;
    });
  }, [files, query, kind]);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search file path or language..."
          className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none md:col-span-2"
        />

        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none"
        >
          {kinds.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>

      <div className="text-sm text-slate-400">
        Showing {filtered.length} of {files.length} files
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <div className="grid grid-cols-12 border-b border-slate-800 bg-slate-900 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <div className="col-span-6">Path</div>
          <div className="col-span-2">Kind</div>
          <div className="col-span-2">Language</div>
          <div className="col-span-2">Open</div>
        </div>

        <div className="divide-y divide-slate-800">
          {filtered.map((file) => (
            <div
              key={file.id}
              className="grid grid-cols-12 bg-slate-950 px-4 py-3 text-sm text-slate-300"
            >
              <div className="col-span-6 break-all text-white">{file.path}</div>
              <div className="col-span-2">{file.file_kind}</div>
              <div className="col-span-2">{file.language || "unknown"}</div>
              <div className="col-span-2">
                <Link
                  href={`/repos/${repoId}/files/${file.id}`}
                  className="rounded-md border border-slate-700 px-2 py-1 text-xs hover:bg-slate-900"
                >
                  View
                </Link>
              </div>
            </div>
          ))}

          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-400">
              No files match your filters.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
