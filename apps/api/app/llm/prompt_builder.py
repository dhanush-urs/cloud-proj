def build_system_prompt() -> str:
    return (
        "You are RepoBrain, an advanced hybrid repository reasoning engine. "
        "Your primary objective is to analyze the provided repository context and answer the user's question accurately. "
        "IMPORTANT RULES:\n"
        "1. First, attempt to answer strictly using the provided repository evidence. Cite the specific file paths and line ranges.\n"
        "2. Do not hallucinate or invent internal files, dependencies, or methods that are not present in the context.\n"
        "3. If the user asks about a code snippet or architecture pattern that is NOT found in the provided evidence, you MUST explicitly state that it is not found in the repository. Provide a general technical explanation as a fallback, but clearly label it as \"General Explanation (Not Grounded in Repo)\".\n"
        "4. Distinguish clearly between Repo-Grounded Facts, Likely Inference, and General Knowledge.\n"
    )


def build_user_prompt(question: str, retrieved_chunks: list[dict], intent: str = "general") -> str:
    context_blocks = []

    if not retrieved_chunks:
        context = "NO REPOSITORY CONTEXT AVAILABLE. The requested snippet or topic was not retrieved from the database."
    else:
        for idx, item in enumerate(retrieved_chunks, start=1):
            file_path = item.get("file_path") or "unknown_file"
            start_line = item.get("start_line")
            end_line = item.get("end_line")
            match_type = item.get("match_type", "chunk")
            location = f"{file_path}:{start_line}-{end_line}" if start_line and end_line else file_path
            snippet = item.get("snippet", "").strip()
            block = (
                f"[Context {idx}] (Type: {match_type})\n"
                f"Location: {location}\n"
                f"Content:\n{snippet}\n"
            )
            context_blocks.append(block)
        context = "\n\n".join(context_blocks)

    return (
        f"USER QUESTION:\n{question}\n\n"
        f"REPOSITORY EVIDENCE:\n{context}\n\n"
        "STRICT OUTPUT RULES — you MUST follow ALL of these:\n"
        "  1. Do NOT use markdown headings: no #, ##, ###\n"
        "  2. Do NOT use bold or italic markers: no **, __, *, _\n"
        "  3. Do NOT use backticks (inline or fenced code blocks)\n"
        "  4. Do NOT use markdown bullet lists (- item or * item)\n"
        "  5. Use plain labeled sections separated by blank lines\n"
        "  6. Use plain numbered lines (1. 2. 3.) if you need a list\n\n"
        "REQUIRED OUTPUT FORMAT (plain labeled fields):\n\n"
        "ANSWER SUMMARY: (1-2 sentence high-level answer)\n\n"
        "REPO-GROUNDED FINDINGS: (facts from the evidence; if none, say None found)\n\n"
        "LIKELY IMPACT OR REASONING: (analysis of consequences or architectural purpose)\n\n"
        "AFFECTED FILES OR SYMBOLS: (list file paths in plain text, one per line, or N/A)\n\n"
        "CONFIDENCE: (HIGH / MEDIUM / LOW — with one-line justification)\n\n"
        "EVIDENCE: (cite file:line ranges in plain text)\n"
    )


def build_repo_summary_prompt(
    question: str,
    retrieved_chunks: list[dict],
) -> str:
    """
    Specialized prompt for REPO_SUMMARY intent.
    Sends structured, pre-ranked evidence (README, metadata, entrypoints, file census)
    and demands a strict plain-text repository overview.
    NO markdown output allowed.
    """
    # Separate evidence by tier for a clean context block
    meta_blocks: list[str] = []
    readme_blocks: list[str] = []
    entrypoint_blocks: list[str] = []
    other_blocks: list[str] = []

    for idx, item in enumerate(retrieved_chunks, start=1):
        mt = item.get("match_type", "chunk")
        fp = item.get("file_path", "unknown")
        snippet = (item.get("snippet") or "").strip()
        block = f"[{mt.upper()}] {fp}\n{snippet[:1500]}"
        if mt in ("repo_metadata", "structure_census"):
            meta_blocks.append(block)
        elif mt == "readme":
            readme_blocks.append(block)
        elif mt in ("entrypoint", "manifest", "symbol_overview"):
            entrypoint_blocks.append(block)
        else:
            other_blocks.append(block)

    context_sections: list[str] = []
    if meta_blocks:
        context_sections.append("REPOSITORY METADATA:\n" + "\n\n".join(meta_blocks))
    if readme_blocks:
        context_sections.append("README / DOCUMENTATION:\n" + "\n\n".join(readme_blocks))
    if entrypoint_blocks:
        context_sections.append("ENTRYPOINTS / MANIFESTS:\n" + "\n\n".join(entrypoint_blocks))
    if other_blocks:
        context_sections.append("OTHER FILES:\n" + "\n\n".join(other_blocks))

    context = "\n\n" + "\n\n".join(context_sections) if context_sections else "NO REPOSITORY CONTEXT FOUND."

    return (
        f"USER QUESTION:\n{question}\n"
        f"{context}\n\n"
        "STRICT OUTPUT RULES — you MUST follow ALL of these:\n"
        "  1. Do NOT use markdown headings: no #, ##, ###\n"
        "  2. Do NOT use bold or italic markers: no **, __, *, _\n"
        "  3. Do NOT use backticks (inline or fenced code blocks)\n"
        "  4. Do NOT use markdown bullet lists (- item or * item)\n"
        "  5. Use plain labeled sections separated by blank lines\n"
        "  6. Use numbered lists (1. 2. 3.) for any list you need\n\n"
        "REQUIRED OUTPUT FORMAT (plain text, labeled fields — no markdown):\n\n"
        "PURPOSE: (1-2 sentences describing what this repository does and why it exists)\n\n"
        "PRIMARY LANGUAGE: (main programming language detected)\n\n"
        "FRAMEWORKS OR TOOLS: (list frameworks/libraries in plain text, one per line)\n\n"
        "MAIN ENTRYPOINTS: (list the main executable or startup files, one per line)\n\n"
        "HOW IT RUNS: (describe how to execute or deploy this project based on evidence)\n\n"
        "KEY COMPONENTS: (list the most important modules, classes, or services, one per line)\n\n"
        "WHAT IT ACTUALLY DOES: (explain the runtime behavior — what the user sees or gets)\n\n"
        "PROJECT SCALE: (starter/demo, small, mid-size, or production-scale — with brief reasoning)\n\n"
        "CONFIDENCE: (HIGH / MEDIUM / LOW — with one-line justification)\n\n"
        "EVIDENCE: (cite file paths and line ranges in plain text, one per line)\n"
    )

def build_line_impact_prompt(
    question: str,
    retrieved_chunks: list[dict],
    line_metadata: dict,
    intent: str = "line_impact",
) -> str:
    """
    Specialized prompt for line-level / rename impact analysis.
    Sends Gemini a structured evidence package.
    Demands strict plain-text output — NO markdown headers, bullets, bold, or backticks.
    """
    found = line_metadata.get("found", False)
    file_path = line_metadata.get("file_path", "unknown")
    line_no = line_metadata.get("line_no", "?")
    line_text = line_metadata.get("line_text", "")
    enclosing = line_metadata.get("enclosing_symbol", "module-level")
    line_type = line_metadata.get("line_type", "other")
    rename_analysis = line_metadata.get("rename_analysis")

    # Build evidence block
    evidence_parts = []
    for idx, item in enumerate(retrieved_chunks, start=1):
        mt = item.get("match_type", "chunk")
        fp = item.get("file_path", "unknown")
        sl = item.get("start_line")
        el = item.get("end_line")
        loc = f"{fp}:{sl}-{el}" if sl and el else fp
        snippet = (item.get("snippet") or "").strip()
        evidence_parts.append(
            f"[Evidence {idx}] type={mt}\n"
            f"Location: {loc}\n"
            f"{snippet}"
        )
    evidence_text = "\n\n---\n\n".join(evidence_parts) if evidence_parts else "NO EVIDENCE FOUND"

    if not found:
        not_found_note = (
            f"\nNOTE: The requested line/snippet was NOT found in the repository "
            f"(searched for: file={line_metadata.get('file_hint','?')}, "
            f"snippet={line_metadata.get('snippet_searched','?')!r}). "
            f"Provide a GENERAL EXPLANATION only. Confidence MUST be LOW."
        )
    else:
        not_found_note = ""

    # Rename analysis section
    rename_block = ""
    if rename_analysis:
        symbol_name = rename_analysis.get("symbol_name", "")
        new_name = rename_analysis.get("new_name", "")
        decl_line = rename_analysis.get("declaration_line", "?")
        refs = rename_analysis.get("same_file_references", [])
        lang = rename_analysis.get("language", "unknown")
        error_if_partial = rename_analysis.get("error_if_partial", f"cannot find symbol: {symbol_name}")

        refs_text = (
            "\n".join(f"  line {r['line_no']}: {r['line_text']}" for r in refs)
            if refs else "  (none found in this file)"
        )
        rename_block = (
            f"\nRENAME ANALYSIS:\n"
            f"  Symbol: {symbol_name}\n"
            f"  New Name: {new_name}\n"
            f"  Declaration Line: {decl_line}\n"
            f"  Language: {lang}\n"
            f"  Same-file references after declaration ({len(refs)}):\n{refs_text}\n"
            f"  Error if declaration-only rename: {error_if_partial}\n"
            f"  Full rename safe: yes (no semantic change)\n"
        )

    return (
        f"USER QUESTION:\n{question}\n\n"
        f"RESOLVED LINE METADATA:\n"
        f"  File: {file_path}\n"
        f"  Line Number: {line_no}\n"
        f"  Line Text: {line_text!r}\n"
        f"  Enclosing Scope: {enclosing}\n"
        f"  Line Type: {line_type}\n"
        f"  Found in Repo: {found}\n"
        f"{not_found_note}"
        f"{rename_block}\n"
        f"REPOSITORY EVIDENCE:\n{evidence_text}\n\n"
        "STRICT OUTPUT RULES — you MUST follow ALL of these:\n"
        "  1. Do NOT use markdown headings: no #, ##, ###\n"
        "  2. Do NOT use bold or italic markers: no **, __, *, _\n"
        "  3. Do NOT use backticks (inline or fenced code blocks)\n"
        "  4. Do NOT use markdown bullet lists (- item or * item)\n"
        "  5. Use plain labeled sections separated by blank lines\n"
        "  6. Use plain numbered lines (1. 2. 3.) if you need a list\n\n"
        "REQUIRED OUTPUT FORMAT (plain text, labeled fields):\n\n"
        "RESOLVED FILE: (state the file path)\n\n"
        "RESOLVED LINE: (state the line number)\n\n"
        "SYMBOL: (state the symbol name if applicable)\n\n"
        "OPERATION: (rename / delete / change / modify)\n\n"
        "WHAT THIS LINE DOES: (explain its purpose in 1-2 plain sentences)\n\n"
        + (
            "CASE A — DECLARATION-ONLY RENAME (BREAKS):\n"
            "(Explain exactly what breaks and list the specific lines still referencing the old name)\n\n"
            "CASE B — FULL CONSISTENT RENAME (SAFE):\n"
            "(Explain that a full rename across all references is safe with no behavioral change)\n\n"
            if rename_analysis else
            "IF DELETED:\n"
            "(Explain direct and downstream consequences of deletion in plain text)\n\n"
        )
        + "IMPACTED FILES: (list file paths in plain text, one per line)\n\n"
        "IMPACTED LINES: (list line numbers and brief description, one per line)\n\n"
        "CONFIDENCE: (HIGH / MEDIUM / LOW with one-line justification)\n\n"
        "EVIDENCE: (cite file:line ranges in plain text)\n"
    )

