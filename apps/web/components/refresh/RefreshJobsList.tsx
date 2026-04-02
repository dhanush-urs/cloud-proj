"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PollingStatus } from "@/components/refresh/PollingStatus";
import { RefreshJobStatusBadge } from "@/components/refresh/RefreshJobStatusBadge";
import { getRepositoryRefreshJobs } from "@/lib/api";
import type { RefreshJob } from "@/lib/types";

type Props = {
  repoId: string;
  initialJobs: RefreshJob[];
};

export function RefreshJobsList({ repoId, initialJobs }: Props) {
  const [jobs, setJobs] = useState<RefreshJob[]>(initialJobs);

  const hasActiveJobs = useMemo(() => {
    return jobs.some((job) =>
      ["queued", "processing", "refreshing", "running"].includes(
        job.status.toLowerCase()
      )
    );
  }, [jobs]);

  useEffect(() => {
    if (!hasActiveJobs) return;

    const intervalId = setInterval(async () => {
      try {
        const latest = await getRepositoryRefreshJobs(repoId);
        setJobs(latest.items);
      } catch {
        // ignore polling failures
      }
    }, 3000);

    return () => clearInterval(intervalId);
  }, [repoId, hasActiveJobs]);

  if (!jobs.length) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">
        No refresh jobs found yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PollingStatus active={hasActiveJobs} />

      <div className="overflow-hidden rounded-xl border border-slate-800">
        <div className="grid grid-cols-12 border-b border-slate-800 bg-slate-900 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <div className="col-span-2">Status</div>
          <div className="col-span-2">Event</div>
          <div className="col-span-2">Branch</div>
          <div className="col-span-2">Changed Files</div>
          <div className="col-span-2">Created</div>
          <div className="col-span-2 text-right">Action</div>
        </div>

        <div className="divide-y divide-slate-800">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="grid grid-cols-12 items-center bg-slate-950 px-4 py-3 text-sm text-slate-300"
            >
              <div className="col-span-2">
                <RefreshJobStatusBadge status={job.status} />
              </div>
              <div className="col-span-2">{job.event_type}</div>
              <div className="col-span-2 truncate">{job.branch || "-"}</div>
              <div className="col-span-2">{job.changed_files.length}</div>
              <div className="col-span-2">
                {new Date(job.created_at).toLocaleTimeString()}
              </div>
              <div className="col-span-2 text-right">
                <Link
                  href={`/repos/${repoId}/refresh-jobs/${job.id}`}
                  className="rounded-md border border-slate-700 px-2 py-1 text-xs transition-colors hover:bg-slate-800 hover:text-white"
                >
                  Details
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
