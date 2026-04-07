#!/data/data/com.termux/files/usr/bin/bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_DIR}/logs"
RUN_LOG="${LOG_DIR}/termux_runs.log"
PIPELINE_SCRIPT="${REPO_DIR}/run_live_pipeline.py"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE_CANDIDATE="${REPO_DIR}/.env"
COMMAND_STRING="${PYTHON_BIN} ${PIPELINE_SCRIPT}"

mkdir -p "${LOG_DIR}"

timestamp() {
    date +"%Y-%m-%dT%H:%M:%S%z"
}

append_log() {
    printf '%s | %s\n' "$(timestamp)" "$1" >> "${RUN_LOG}"
}

send_notification() {
    local title="$1"
    local content="$2"
    if command -v termux-notification >/dev/null 2>&1; then
        termux-notification --title "${title}" --content "${content}" >/dev/null 2>&1 || true
    fi
}

fail_run() {
    local reason="$1"
    append_log "STATUS=FAILURE | ${reason}"
    send_notification "Observation Run Failed" "${reason}"
    exit 1
}

append_log "START | command=${COMMAND_STRING}"

if [ ! -d "${REPO_DIR}" ]; then
    fail_run "repo missing: ${REPO_DIR}"
fi

if [ ! -f "${PIPELINE_SCRIPT}" ]; then
    fail_run "pipeline script missing: ${PIPELINE_SCRIPT}"
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    fail_run "python missing: ${PYTHON_BIN}"
fi

cd "${REPO_DIR}" || fail_run "cannot cd into repo: ${REPO_DIR}"

if [ -f "${ENV_FILE_CANDIDATE}" ]; then
    export SIGNAL_FORGE_ENV_FILE="${SIGNAL_FORGE_ENV_FILE:-${ENV_FILE_CANDIDATE}}"
fi

OUTPUT_FILE="$(mktemp)"
if ! "${PYTHON_BIN}" "${PIPELINE_SCRIPT}" >"${OUTPUT_FILE}" 2>&1; then
    while IFS= read -r line; do
        append_log "${line}"
    done < "${OUTPUT_FILE}"
    rm -f "${OUTPUT_FILE}"
    fail_run "pipeline exited non-zero"
fi

PIPELINE_OUTPUT="$(cat "${OUTPUT_FILE}")"
while IFS= read -r line; do
    append_log "${line}"
done < "${OUTPUT_FILE}"
rm -f "${OUTPUT_FILE}"

if printf '%s\n' "${PIPELINE_OUTPUT}" | grep -q "DATA FETCH FAILED — SKIPPING RUN"; then
    fail_run "pipeline skipped: data fetch failed"
fi

REGIME_LINE="$(printf '%s\n' "${PIPELINE_OUTPUT}" | grep -m1 '^REGIME:' || true)"
if [ -n "${REGIME_LINE}" ]; then
    append_log "STATUS=SUCCESS | ${REGIME_LINE}"
    send_notification "Observation Run Complete" "REGIME logged"
else
    fail_run "pipeline completed without regime output"
fi

exit 0
