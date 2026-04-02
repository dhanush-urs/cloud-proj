import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { PageHeader } from "@/components/common/PageHeader";
import { RepoSubnav } from "@/components/layout/RepoSubnav";
import { getHotspots } from "@/lib/api";

type Props = {
  params: Promise<{ repoId: string }>;
};

function riskTone(
  level: string
): "default" | "green" | "yellow" | "red" | "blue" {
  if (level === "critical" || level === "high") return "red";
  if (level === "medium") return "yellow";
  if (level === "low") return "green";
  return "default";
}

export default async function RepoHotspotsPage({ params }: Props) {
  const { repoId } = await params;

  let data = null;

  try {
    data = await getHotspots(repoId);
  } catch {
    data = null;
  }

  return (
    <div>
      <PageHeader
        title="Risk Hotspots"
        subtitle="Files that deserve extra engineering attention."
      />

      <RepoSubnav repoId={repoId} />

      {!data || data.items.length === 0 ? (
        <EmptyState
          title="No hotspots available"
          description="Make sure the repository has been parsed before viewing hotspots."
        />
      ) : (
        <div className="grid gap-4">
          {data.items.map((item) => (
            <Card key={item.file_id}>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="text-lg font-semibold text-white">
                    {item.path}
                  </div>
                  <div className="mt-1 text-sm text-slate-400">
                    {item.language || "unknown"} • {item.file_kind}
                  </div>
                </div>
                <Badge
                  label={`${item.risk_level} (${item.risk_score})`}
                  tone={riskTone(item.risk_level)}
                />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-4 text-sm text-slate-300">
                <div>Complexity: {item.complexity_score}</div>
                <div>Dependency: {item.dependency_score}</div>
                <div>Inbound: {item.inbound_dependencies}</div>
                <div>Outbound: {item.outbound_dependencies}</div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
