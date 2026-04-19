"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an instrumentation service
    console.error("[RootError]", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center p-8 text-center">
      <div className="mb-6 rounded-full bg-red-500/10 p-4 text-red-500">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 className="mb-2 text-2xl font-bold text-white">Application Error</h2>
      <p className="mb-8 max-w-md text-slate-400">
        The application encountered an unexpected runtime error. We've logged the
        incident and are looking into it.
      </p>
      <div className="flex gap-4">
        <button
          onClick={() => reset()}
          className="rounded-lg bg-indigo-600 px-6 py-2 font-semibold text-white transition-colors hover:bg-indigo-500"
        >
          Try Again
        </button>
        <button
          onClick={() => (window.location.href = "/repos")}
          className="rounded-lg border border-slate-700 px-6 py-2 font-semibold text-slate-300 transition-colors hover:bg-slate-900"
        >
          Return to Repos
        </button>
      </div>
    </div>
  );
}
