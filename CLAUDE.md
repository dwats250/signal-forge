# OpenWolf

@.wolf/OPENWOLF.md

Read and follow `.wolf/OPENWOLF.md` every session. Check `.wolf/cerebrum.md` before generating code. Check `.wolf/anatomy.md` before reading files.


# Signal Forge — Claude Instructions

## System Intent

- Signal Forge is a trading decision system, not a generic software project.
- Preserve trading context and operator-facing decision support.
- SIL is manual, structured, and non-AI.
- All logic must map to real market behavior or execution discipline.
- Do NOT implement changes that do not clearly improve decision quality or map to real market edge.

## Discipline

- Use repository documentation as source of truth.
- Read only files required for the task.
- Do NOT scan the entire repository unless explicitly instructed.
- Avoid re-reading files already inspected unless necessary.
- Do NOT restate architecture unless necessary.
- Avoid repeating prior outputs.

## Scope Control

- If task scope expands → STOP and propose a short plan.
- If edge impact is unclear → STOP and ask for clarification.
- Do NOT proceed with broad analysis without confirmation.
- Do NOT redesign architecture unless explicitly requested.
- Do NOT introduce new abstractions unless required.
- Stay within defined task boundaries.

## Output

- Prefer diffs over full file rewrites.
- Prefer bullet points over paragraphs.
- For non-trivial changes, state the problem being solved and why the change improves the system.
- Return only requested output.
