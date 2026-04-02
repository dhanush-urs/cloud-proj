import Link from "next/link";
import { getRepositories } from "@/lib/api";
import type { Repository } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ReposPage() {
  let repos: Repository[] = [];
  let error: string | null = null;

  try {
    const fetched = await getRepositories();
    repos = fetched;
  } catch (err) {
    console.error("Failed to fetch repositories:", err);
    error = err instanceof Error ? err.message : "Failed to load repositories. Please check your connection.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Repositories</h1>
        <Link
          href="/"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
        >
          Add Repository
        </Link>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-900 bg-rose-500/10 p-6 text-rose-300">
          <h2 className="mb-1 font-bold italic tracking-tight uppercase text-rose-400">Connection Error</h2>
          <p className="text-sm opacity-90">{error}</p>
          <Link 
            href="/repositories"
            className="mt-4 inline-block text-xs font-semibold text-rose-400 underline hover:text-rose-300"
          >
            Try Again
          </Link>
        </div>
      ) : repos.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-slate-400">
          No repositories found yet.
        </div>
      ) : (
        <div className="grid gap-4">
          {repos.map((repo) => (
            <Link
              key={repo.id}
              href={`/repositories/${repo.id}`}
              className="group block rounded-xl border border-slate-800 bg-slate-900/50 p-5 transition-all hover:border-slate-700 hover:bg-slate-800"
            >
              <div className="flex items-start justify-between sm:items-center">
                <div className="space-y-1">
                  <div className="text-xl font-semibold text-white group-hover:text-blue-400">
                    {repo.repo_url}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-400">
                    <span>
                      Branch: <span className="text-slate-300">{repo.default_branch}</span>
                    </span>
                    <span className="text-slate-700">•</span>
                    <span>
                      Status: <span className={repo.status === "failed" ? "text-rose-400 font-semibold" : "text-slate-300"}>{repo.status}</span>
                    </span>
                  </div>
                  {repo.status === "failed" && repo.last_error && (
                    <div className="mt-2 rounded bg-rose-500/10 border border-rose-500/20 px-3 py-2 text-xs text-rose-300">
                      <span className="font-bold">Failure Reason:</span> {repo.last_error}
                    </div>
                  )}
                </div>
                <div className="hidden text-slate-500 sm:block">
                  <svg
                    className="h-5 w-5 transition-transform group-hover:translate-x-1"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
