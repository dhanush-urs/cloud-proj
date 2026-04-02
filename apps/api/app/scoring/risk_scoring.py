def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def compute_complexity_score(
    line_count: int,
    symbol_count: int,
    file_kind: str,
) -> float:
    line_component = min(line_count / 8.0, 40.0)
    symbol_component = min(symbol_count * 1.8, 35.0)

    kind_bonus = 0.0
    if file_kind == "source":
        kind_bonus = 12.0
    elif file_kind == "config":
        kind_bonus = 6.0
    elif file_kind == "test":
        kind_bonus = -6.0

    return clamp(line_component + symbol_component + kind_bonus)


def compute_dependency_score(
    inbound_dependencies: int,
    outbound_dependencies: int,
) -> float:
    inbound_component = min(inbound_dependencies * 7.5, 55.0)
    outbound_component = min(outbound_dependencies * 4.5, 30.0)

    return clamp(inbound_component + outbound_component)


def compute_change_proneness_score(
    line_count: int,
    is_generated: bool,
    is_vendor: bool,
) -> float:
    if is_generated or is_vendor:
        return 0.0

    # Temporary proxy until git churn history is added in later module
    if line_count < 50:
        return 18.0
    if line_count < 200:
        return 28.0
    if line_count < 500:
        return 40.0
    return 52.0


def compute_test_proximity_score(
    path: str,
    file_kind: str,
) -> float:
    normalized = path.lower()

    if file_kind == "test":
        return 0.0

    if "test" in normalized or "spec" in normalized:
        return 8.0

    # No obvious test adjacency => higher risk
    return 22.0


def compute_total_risk_score(
    complexity_score: float,
    dependency_score: float,
    change_proneness_score: float,
    test_proximity_score: float,
) -> float:
    score = (
        complexity_score * 0.35
        + dependency_score * 0.35
        + change_proneness_score * 0.20
        + test_proximity_score * 0.10
    )
    return round(clamp(score), 2)


def classify_risk_level(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
