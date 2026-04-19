"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createRepository } from "@/lib/api";

export function CreateRepoForm() {
  const router = useRouter();
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      const repo = await createRepository({
        repo_url: repoUrl,
        branch,
      });

      if (!repo || !repo.id) {
        throw new Error("Failed to create repository: No data returned from API.");
      }

      router.push(`/repos/${repo.id}`);
      router.refresh();
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Failed to create repository"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <label className="mb-1 block text-sm text-slate-300">
          GitHub Repository URL
        </label>
        <input
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none"
          placeholder="https://github.com/owner/repo"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm text-slate-300">Branch</label>
        <input
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none"
          placeholder="main"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {loading ? "Creating..." : "Add Repository"}
      </button>

      {message ? <p className="text-sm text-slate-300">{message}</p> : null}
    </form>
  );
}
