import { Badge } from "@/components/common/Badge";

type Props = {
  status: string;
};

function statusTone(
  status: string
): "default" | "green" | "yellow" | "red" | "blue" {
  const normalized = status.toLowerCase();

  if (
    normalized === "parsed" ||
    normalized === "ready" ||
    normalized === "completed"
  ) {
    return "green";
  }

  if (
    normalized === "parsing" ||
    normalized === "embedding" ||
    normalized === "processing"
  ) {
    return "yellow";
  }

  if (normalized === "failed" || normalized === "error") {
    return "red";
  }

  return "default";
}

export function RepoStatusBadge({ status }: Props) {
  return <Badge label={status} tone={statusTone(status)} />;
}
