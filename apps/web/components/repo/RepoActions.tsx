"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ActionConsole } from "@/components/common/ActionConsole";
import { RepoStatusBadge } from "@/components/repo/RepoStatusBadge";
import { getRepository, getJobs, triggerEmbed, triggerParse } from "@/lib/api";
import type { Repository } from "@/lib/types";

type Props = {
  repoId: string;
  initialStatus?: string;
};

export function RepoActions({ repoId, initialStatus = "unknown" }: Props) {
  const router = useRouter();
  const [loadingAction, setLoadingAction] = useState<"parse" | "embed" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [polling, setPolling] = useState(false);

  const currentStatus = repo?.status || initialStatus;

  // Compute states strictly
  const isProcessing = useMemo(() => {
    const s = (currentStatus || "").toLowerCase();
    return ["queued", "running", "parsing", "indexing", "embedding", "processing"].includes(s);
  }, [currentStatus]);

  const isEmbedAllowed = useMemo(() => {
    const s = (currentStatus || "").toLowerCase();
    return ["parsed"].includes(s);
  }, [currentStatus]);

  const isParseAllowed = useMemo(() => {
    const s = (currentStatus || "").toLowerCase();
    return ["connected", "failed", "parsed", "indexed", "embedded"].includes(s);
  }, [currentStatus]);

  // Polling logic
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    let isMounted = true;

    async function refreshData() {
      if (!isMounted) return;
      try {
        const latest = await getRepository(repoId);
        
        // Fetch real status text from the latest job so Action Console is truthful
        try {
          const jobsRes = await getJobs(repoId, 1);
          if (jobsRes.items && jobsRes.items.length > 0) {
            setMessage(jobsRes.items[0].message || "Processing...");
          }
        } catch {
          // ignore job fetch errors
        }

        if (latest.status !== currentStatus) {
          router.refresh(); // Trigger Server Component re-render
        }
        setRepo(latest);
      } catch {
        // ignore polling failures gracefully
      }
    }

    if (isProcessing) {
      setPolling(true);
      // Fetch immediately on mount if processing, and update action console
      refreshData();
      intervalId = setInterval(refreshData, 2000);
    } else {
      setPolling(false);
    }

    return () => {
      isMounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [repoId, isProcessing, currentStatus, router]);

  async function handleParse() {
    setLoadingAction("parse");
    setMessage("Triggering real backend parse...");

    try {
      const result = await triggerParse(repoId);
      setMessage(result.message || "Parse queued successfully");
      const latest = await getRepository(repoId);
      if (latest.status !== currentStatus) {
        router.refresh();
      }
      setRepo(latest);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to trigger parse");
    } finally {
      setLoadingAction(null);
    }
  }

  async function handleEmbed() {
    setLoadingAction("embed");
    setMessage("Triggering semantic embed...");

    try {
      const result = await triggerEmbed(repoId);
      setMessage(result.message || `Embed queued successfully`);
      const latest = await getRepository(repoId);
      if (latest.status !== currentStatus) {
        router.refresh();
      }
      setRepo(latest);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to trigger embed");
    } finally {
      setLoadingAction(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
        <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
          Current Status
        </div>
        <div className="flex items-center gap-3">
          <RepoStatusBadge status={currentStatus} />
          {polling ? (
            <span className="text-xs text-amber-300 animate-pulse">
              Syncing from backend...
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleParse}
          disabled={loadingAction !== null || isProcessing || !isParseAllowed}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loadingAction === "parse" ? "Parsing..." : "Parse Repository"}
        </button>

        <button
          onClick={handleEmbed}
          disabled={loadingAction !== null || isProcessing || !isEmbedAllowed}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loadingAction === "embed" ? "Embedding..." : "Embed Repository"}
        </button>
      </div>

      <ActionConsole message={message} />
    </div>
  );
}
