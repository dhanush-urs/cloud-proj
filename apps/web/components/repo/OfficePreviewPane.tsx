"use client";

import { useEffect, useMemo, useState } from "react";

type Props = {
  previewUrl: string;
  rawUrl: string;
  filename: string;
};

type PreviewMeta = {
  available: boolean;
  media_type: string | null;
  preview_url: string | null;
  message: string | null;
};

export function OfficePreviewPane({ previewUrl, rawUrl, filename }: Props) {
  const [meta, setMeta] = useState<PreviewMeta | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const res = await fetch(`${previewUrl}?metadata=1`, { cache: "no-store" });
        const data = (await res.json()) as PreviewMeta;
        if (!cancelled) setMeta(data);
      } catch {
        if (!cancelled) {
          setMeta({
            available: false,
            media_type: null,
            preview_url: null,
            message:
              "Inline preview is unavailable in this environment. You can still open the raw file.",
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [previewUrl]);

  const inlineUrl = useMemo(() => previewUrl, [previewUrl]);

  return (
    <div className="h-[800px] w-full bg-slate-900/50 flex flex-col">
      <div className="bg-slate-900 border-b border-slate-800 px-4 py-2 flex justify-between items-center text-[10px] text-slate-500 font-mono">
        <span>PRESENTATION PREVIEW</span>
        <a href={rawUrl} download={filename || true} className="text-blue-400 hover:underline">
          Open Raw Asset ↗
        </a>
      </div>
      <div className="flex-1 relative">
        {loading ? (
          <div className="h-full w-full flex items-center justify-center text-sm text-slate-400">
            Generating preview...
          </div>
        ) : meta?.available ? (
          meta.media_type?.startsWith("image/") ? (
            <div className="h-full w-full flex items-center justify-center p-6">
              <img src={inlineUrl} alt="Presentation preview" className="max-w-full max-h-full rounded border border-slate-700" />
            </div>
          ) : (
            <iframe src={inlineUrl} className="h-full w-full border-0 absolute inset-0" title="Presentation Preview" />
          )
        ) : (
          <div className="h-full w-full flex items-center justify-center bg-slate-950 p-6 text-center">
            <div className="max-w-sm space-y-3">
              <p className="text-sm text-slate-300">
                {meta?.message ||
                  "Inline preview is unavailable in this environment. You can still open the raw file."}
              </p>
              {/* No download attribute — avoids Safari auto-download popup */}
              <a
                href={rawUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
              >
                Open Raw Asset ↗
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
