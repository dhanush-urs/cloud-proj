def build_system_prompt() -> str:
    return (
        "You are RepoBrain, a repository assistant.\n"
        "Answer the user's exact question using only the provided repository context.\n"
        "Be specific and helpful. If context is partial, clearly separate explicit facts from inferences.\n"
        "Do not invent files, symbols, or behaviors not present in context.\n"
        "Do not output template labels like Direct Answer, Evidence, Confidence, or Analysis.\n"
    )


def build_user_prompt(question: str, retrieved_chunks: list[dict], intent: str = "general") -> str:
    context = _format_context(retrieved_chunks)
    return (
        f"Question: {question}\n\n"
        f"Repository Context:\n{context}\n\n"
        "Answer the question directly and naturally."
    )


def build_repo_summary_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    return build_user_prompt(question, retrieved_chunks, intent="repo_summary")


def build_code_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    return build_user_prompt(question, retrieved_chunks, intent="code")


def build_impact_prompt(
    question: str,
    retrieved_chunks: list[dict],
    line_metadata: dict,
) -> str:
    return build_user_prompt(question, retrieved_chunks, intent="impact")


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return "NO REPO EVIDENCE FOUND."

    blocks = []
    for idx, c in enumerate(chunks, 1):
        fp = c.get("file_path") or "unknown"
        sl = c.get("start_line")
        el = c.get("end_line")
        loc = f"{fp}:{sl}-{el}" if sl else fp
        mt = c.get("match_type", "chunk")
        snippet = c.get("snippet", "").strip()
        blocks.append(f"[{idx}] {loc} (Type: {mt})\n{snippet}")

    return "\n\n---\n\n".join(blocks)
