# Termux Morning Flow

6:00 AM
- Build Morning Edge reports with `/home/dustin/signal-forge/scripts/run_reports_termux.sh`

6:30 AM
- Run live observation with `/home/dustin/signal-forge/scripts/run_observation_termux.sh`
- Review `SPY`, `NVDA`, `AAPL`, and `TSLA`
- Record the morning entry

Tasker
- Install `Termux`, `Tasker`, and `Termux:Tasker`
- Create one Tasker profile scheduled for `6:00 AM`, weekdays
- Run `/home/dustin/signal-forge/scripts/run_reports_termux.sh`
- Create a second Tasker profile scheduled for `6:30 AM`, weekdays
- Run `/home/dustin/signal-forge/scripts/run_observation_termux.sh`

Cron fallback
- Use Termux `crond`
- Add these lines to your crontab:
- `0 6 * * 1-5 /data/data/com.termux/files/usr/bin/bash /home/dustin/signal-forge/scripts/run_reports_termux.sh`
- `30 6 * * 1-5 /data/data/com.termux/files/usr/bin/bash /home/dustin/signal-forge/scripts/run_observation_termux.sh`

DuckDNS
- Disabled from active automation intentionally
- Archived at `/home/dustin/signal-forge/scripts/disabled/duckdns_update.sh`

Logs
- Report build log: `/home/dustin/signal-forge/logs/morning_reports.log`
- Legacy combined log: `/home/dustin/signal-forge/logs/morning_edge.log`
- Pipeline logs: `/home/dustin/signal-forge/signal_forge/logs/live_pipeline_audit.jsonl`
- Decision log: `/home/dustin/signal-forge/signal_forge/logs/decision_log.jsonl`
