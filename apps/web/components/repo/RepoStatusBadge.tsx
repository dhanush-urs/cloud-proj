import { Badge } from "@/components/common/Badge";

type Props = {
  status: string;
};

function statusTone(
  status: string
): "default" | "green" | "yellow" | "red" | "blue" {
  const normalized = status.toLowerCase();

  if (
    ["parsed", "indexed", "embedded", "ready", "success", "completed"].includes(normalized)
  ) {
    return "green";
  }

  if (
    ["parsing", "indexing", "embedding", "processing", "queued", "running"].includes(normalized)
  ) {
    return "yellow";
  }

  if (normalized === "failed" || normalized === "error") {
    return "red";
  }

  if (normalized === "connected") {
    return "blue";
  }

  return "default";
}

export function RepoStatusBadge({ status }: Props) {
  return <Badge label={status} tone={statusTone(status)} />;
}
