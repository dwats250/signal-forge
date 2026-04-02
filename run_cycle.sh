#!/bin/bash

cd ~/signal-forge || exit

echo "🔄 Pulling latest..."
git pull

echo "🤖 Running Claude (planning)..."
claude <<'CLAUDE'
Read docs/PRDs/dislocation_engine.md
Update docs/NEXT_STEPS.md with a phased plan
Do not implement anything
CLAUDE

echo "🧠 Plan ready. Review docs/NEXT_STEPS.md before continuing."
read -p "Proceed with Codex Phase execution? (y/n): " confirm

if [[ "$confirm" != "y" ]]; then
  echo "🛑 Stopping before execution."
  exit 0
fi

echo "⚙️ Running Codex (build phase)..."
codex <<'CODEX'
Read docs/NEXT_STEPS.md
Execute Phase 1 only
Update docs/DEV_LOG.md
Write diff to artifacts/latest_patch.diff
CODEX

echo "📊 Building reports..."
python3 -m reports.build_all

echo "📦 Committing changes..."
git add .
git commit -m "auto: PRD cycle execution"
git push

echo "✅ Done. Signal Forge cycle complete."
