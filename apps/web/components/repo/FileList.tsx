import type { FileRecord } from "@/lib/types";

type Props = {
  files: FileRecord[];
};

export function FileList({ files }: Props) {
  if (!files.length) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">
        No indexed files available yet.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-800">
      <div className="grid grid-cols-12 border-b border-slate-800 bg-slate-900 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <div className="col-span-6">Path</div>
        <div className="col-span-2">Kind</div>
        <div className="col-span-2">Language</div>
        <div className="col-span-2">Lines</div>
      </div>

      <div className="divide-y divide-slate-800">
        {files.map((file) => (
          <div
            key={file.id}
            className="grid grid-cols-12 bg-slate-950 px-4 py-3 text-sm text-slate-300"
          >
            <div className="col-span-6 break-all text-white">{file.path}</div>
            <div className="col-span-2">{file.file_kind}</div>
            <div className="col-span-2">{file.language || "unknown"}</div>
            <div className="col-span-2">{file.line_count ?? "-"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
