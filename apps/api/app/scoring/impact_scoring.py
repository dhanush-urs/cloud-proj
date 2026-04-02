def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def compute_file_impact_score(
    depth: int,
    inbound_dependencies: int,
    outbound_dependencies: int,
    risk_score: float,
) -> float:
    depth_multiplier = max(1.0, 4.0 - (depth * 0.8))

    base = (
        inbound_dependencies * 5.0
        + outbound_dependencies * 2.5
        + risk_score * 0.7
    )

    return round(clamp(base * depth_multiplier), 2)


def compute_total_impact_score(file_scores: list[float]) -> float:
    if not file_scores:
        return 0.0

    # Weighted by top impactful files
    top_scores = sorted(file_scores, reverse=True)[:10]
    total = sum(top_scores) / max(1, min(len(top_scores), 5))
    return round(clamp(total), 2)


def classify_impact_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 25:
        return "medium"
    return "low"
