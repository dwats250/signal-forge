#!/data/data/com.termux/files/usr/bin/bash

set -u

cd /home/dustin/signal-forge || exit 1

mkdir -p logs

echo "=== MORNING EDGE RUN $(date) ===" >> logs/morning_edge.log

# Legacy convenience wrapper: keep report generation sourced from build_all only.
python3 -m reports.build_all >> logs/morning_edge.log 2>&1
python3 run_live_pipeline.py >> logs/morning_edge.log 2>&1

echo "=== COMPLETE ===" >> logs/morning_edge.log
