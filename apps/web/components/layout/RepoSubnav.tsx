"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type Props = {
  repoId: string;
};

const links = [
  { href: "", label: "Overview" },
  { href: "/files", label: "Files" },
  { href: "/search", label: "Search" },
  { href: "/chat", label: "Ask Repo" },
  // { href: "/hotspots", label: "Hotspots" },
  // { href: "/onboarding", label: "Onboarding" },
  // { href: "/impact", label: "PR Impact" },
  { href: "/refresh-jobs", label: "Refresh Jobs" },
];

export function RepoSubnav({ repoId }: Props) {
  const pathname = usePathname();

  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {links.map((link) => {
        const fullPath = `/repos/${repoId}${link.href}`;
        const isActive =
          pathname === fullPath ||
          (link.href !== "" && pathname.startsWith(fullPath));

        return (
          <Link
            key={link.label}
            href={fullPath}
            className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
              isActive
                ? "border-indigo-500 bg-indigo-500/10 text-indigo-400"
                : "border-slate-800 bg-slate-900 text-slate-300 hover:bg-slate-800"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </div>
  );
}
