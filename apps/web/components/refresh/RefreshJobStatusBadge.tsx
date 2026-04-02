import { Badge } from "@/components/common/Badge";

type Props = {
  status: string;
};

function toneForStatus(
  status: string
): "default" | "green" | "yellow" | "red" | "blue" {
  const s = status.toLowerCase();

  if (["completed", "success", "done"].includes(s)) return "green";
  if (["queued", "processing", "refreshing", "running"].includes(s))
    return "yellow";
  if (["failed", "error"].includes(s)) return "red";
  if (["refresh_pending"].includes(s)) return "blue";

  return "default";
}

export function RefreshJobStatusBadge({ status }: Props) {
  return <Badge label={status} tone={toneForStatus(status)} />;
}
