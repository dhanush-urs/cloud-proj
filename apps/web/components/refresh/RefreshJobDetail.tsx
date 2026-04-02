"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/common/Card";
import { PollingStatus } from "@/components/refresh/PollingStatus";
import { RefreshJobStatusBadge } from "@/components/refresh/RefreshJobStatusBadge";
import { getRefreshJob } from "@/lib/api";
import type { RefreshJob } from "@/lib/types";

type Props = {
  initialJob: RefreshJob;
};

export function RefreshJobDetail({ initialJob }: Props) {
  const [job, setJob] = useState<RefreshJob>(initialJob);

  const active = useMemo(() => {
    return ["queued", "processing", "refreshing", "running"].includes(
      job.status.toLowerCase()
    );
  }, [job.status]);

  useEffect(() => {
    if (!active) return;

    const intervalId = setInterval(async () => {
      try {
        const latest = await getRefreshJob(job.id);
        setJob(latest);
      } catch {
        // ignore polling failures
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [job.id, active]);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <PollingStatus active={active} />
        <RefreshJobStatusBadge status={job.status} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="md:col-span-2">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-white">Summary</h2>
            <p className="mt-1 text-sm text-slate-300">
              {job.summary || "No summary available."}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 text-sm text-slate-300">
            <div>
              <span className="text-slate-400 block mb-1">Event Type</span>
              <div className="text-white font-medium">{job.event_type}</div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1">Trigger Source</span>
              <div className="text-white font-medium">{job.trigger_source}</div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1">Branch</span>
              <div className="text-white font-medium">{job.branch || "-"}</div>
            </div>

            <div>
              <span className="text-slate-400 block mb-1">Created</span>
              <div className="text-white font-medium">
                {new Date(job.created_at).toLocaleString()}
              </div>
            </div>

            {job.updated_at && (
              <div>
                <span className="text-slate-400 block mb-1">Last Updated</span>
                <div className="text-white font-medium">
                  {new Date(job.updated_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-semibold text-white">Metadata</h2>
          <div className="space-y-3 text-xs">
            <div>
              <div className="text-slate-500 mb-1 uppercase tracking-wider font-bold">
                Job ID
              </div>
              <div className="font-mono text-slate-300 p-2 bg-slate-950 rounded break-all border border-slate-800">
                {job.id}
              </div>
            </div>
            <div>
              <div className="text-slate-500 mb-1 uppercase tracking-wider font-bold">
                Repository ID
              </div>
              <div className="font-mono text-slate-300 p-2 bg-slate-950 rounded break-all border border-slate-800">
                {job.repository_id}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {job.error_message && (
        <Card className="border-rose-900/50 bg-rose-950/10">
          <h2 className="mb-3 text-lg font-semibold text-rose-300">
            Error Logs
          </h2>
          <pre className="rounded-lg bg-slate-950 p-4 text-xs text-rose-200 border border-rose-900/30 overflow-x-auto">
            {job.error_message}
          </pre>
        </Card>
      )}

      <Card>
        <h2 className="mb-3 text-lg font-semibold text-white">
          Changed Files ({job.changed_files.length})
        </h2>
        {job.changed_files.length ? (
          <div className="space-y-1">
            {job.changed_files.map((file, index) => (
              <div
                key={`${file}-${index}`}
                className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-300 hover:bg-slate-900 transition-colors"
              >
                {file}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400 italic">
            No specific changed files recorded for this event.
          </p>
        )}
      </Card>
    </div>
  );
}
