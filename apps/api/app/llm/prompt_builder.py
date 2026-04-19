def build_system_prompt() -> str:
    return (
        "You are RepoBrain, an expert software engineering assistant with deep knowledge of "
        "codebases, architecture, and software design. "
        "Answer as a knowledgeable colleague explaining things clearly to a fellow developer. "
        "PRINCIPLES:\n"
        "1. CONVERSATIONAL: Write in clear, natural English — no robotic bullet dumps or raw metadata.\n"
        "2. GROUNDED: Base your answers strictly on the repository context provided. Cite files.\n"
        "3. CONCRETE: Name specific files, functions, and patterns found in the evidence.\n"
        "4. HELPFUL: Give the developer what they actually need — explanation, not just retrieval.\n"
        "5. FORMATTED: Use Markdown for readability — headers, **bold**, `code`, bullet lists.\n"
    )


def build_user_prompt(question: str, retrieved_chunks: list[dict], intent: str = "general") -> str:
    context = _format_context(retrieved_chunks)
    return (
        f"QUESTION: {question}\n\n"
        f"REPOSITORY CONTEXT:\n{context}\n\n"
        "Answer conversationally and concisely. Structure your response as:\n"
        "1. A direct answer paragraph (2-4 sentences)\n"
        "2. Key details with specific file/function references from the context\n"
        "3. Any important caveats or edge cases\n\n"
        "Do NOT output raw metadata fields. Write like a senior engineer explaining to a colleague."
    )


def build_repo_summary_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    context = _format_context(retrieved_chunks)
    return (
        f"QUESTION: {question}\n\n"
        f"WHOLE-REPO BRIEFING (Context):\n{context}\n\n"
        "You are a senior software architect analyzing an internal repository. The user has asked a broad question "
        "about the repository (e.g., 'what does this repo do', 'explain the architecture').\n\n"
        "Analyze the provided whole-repo briefing—especially the REPO INTELLIGENCE ARTIFACT, README, and entry point files—to "
        "synthesize a comprehensive, high-level explanation. Do NOT act like a search engine returning citations. "
        "Do NOT just dump file counts, metadata, or generic lists.\n\n"
        "Write in natural, flowing paragraphs and structure your response with these exact markdown headers:\n"
        "### Overview\n"
        "(Explain what the project actually is and its main business purpose in 2-4 sentences.)\n\n"
        "### How it Works\n"
        "(Explain the main execution flow, user journey, or core mechanism of the app.)\n\n"
        "### Architecture & Main Files\n"
        "(Describe the structural layout and high-level responsibilities of key directories/files.)\n\n"
        "### Tech Stack & Data Flow\n"
        "(Summarize the primary languages, frameworks, UI/Backend split, and database/data models.)\n\n"
        "**STRICT GROUNDING RULES:**\n"
        "- DO NOT report a Database (e.g., PostgreSQL, MongoDB) unless you see an explicit connection string, config, or ORM model in the evidence.\n"
        "- DO NOT report a Framework (e.g., Express, FastAPI) unless you see it in the dependency manifest or entry point imports.\n"
        "- If you see a CSV file like `capitals.csv`, explain that the app likely reads and processes this data.\n\n"
        "Write clearly and confidently. If you see 'WorldCapitals-Quiz' or similar, explain it as an app, not just a repo name. "
        "Keep file references organic and conversational. If evidence is missing for a specific section, state clearly: 'No specific evidence found for [section]'."
    )


def build_code_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    context = _format_context(retrieved_chunks)
    return (
        f"QUESTION: {question}\n\n"
        f"CODE EVIDENCE:\n{context}\n\n"
        "Answer conversationally. Explain:\n"
        "1. What this code does in plain English\n"
        "2. The key logic steps with specific line references\n"
        "3. Where it's used in the wider codebase\n"
        "4. Any important patterns or potential issues\n\n"
        "Write like a senior engineer doing a code review walkthrough."
    )


def build_impact_prompt(
    question: str,
    retrieved_chunks: list[dict],
    line_metadata: dict,
) -> str:
    context = _format_context(retrieved_chunks)
    file_path = line_metadata.get("file_path") or "unknown"
    line_no = line_metadata.get("line_no") or "?"
    line_text = line_metadata.get("line_text") or "N/A"

    return (
        f"QUESTION: {question}\n\n"
        f"TARGET LINE:\n"
        f"  File: {file_path} (line {line_no})\n"
        f"  Code: `{line_text.strip()}`\n\n"
        f"AVAILABLE EVIDENCE:\n{context}\n\n"
        "Explain the impact of deleting or changing this line in plain English. Structure as:\n"
        "1. **What this line does** — concrete explanation\n"
        "2. **What breaks** — specific callers, features, or behaviors affected\n"
        "3. **What still works** — unaffected paths\n"
        "4. **Failure type** — visual / build-time / runtime / config / data\n"
        "5. **Severity** — LOW / MEDIUM / HIGH with one-line justification\n\n"
        "Be specific and grounded in the evidence. No generic templates."
    )


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
