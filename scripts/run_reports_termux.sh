#!/data/data/com.termux/files/usr/bin/bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_DIR}/logs"
RUN_LOG="${LOG_DIR}/morning_reports.log"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE_CANDIDATE="${REPO_DIR}/.env"

mkdir -p "${LOG_DIR}"

timestamp() {
    date +"%Y-%m-%dT%H:%M:%S%z"
}

append_log() {
    printf '%s | %s\n' "$(timestamp)" "$1" >> "${RUN_LOG}"
}

append_log "START | command=${PYTHON_BIN} -m reports.build_all"

cd "${REPO_DIR}" || {
    append_log "STATUS=FAILURE | cannot cd into repo: ${REPO_DIR}"
    exit 1
}

if [ -f "${ENV_FILE_CANDIDATE}" ]; then
    export SIGNAL_FORGE_ENV_FILE="${SIGNAL_FORGE_ENV_FILE:-${ENV_FILE_CANDIDATE}}"
fi

OUTPUT_FILE="$(mktemp)"
if ! "${PYTHON_BIN}" -m reports.build_all >"${OUTPUT_FILE}" 2>&1; then
    while IFS= read -r line; do
        append_log "${line}"
    done < "${OUTPUT_FILE}"
    rm -f "${OUTPUT_FILE}"
    append_log "STATUS=FAILURE | reports.build_all exited non-zero"
    exit 1
fi

while IFS= read -r line; do
    append_log "${line}"
done < "${OUTPUT_FILE}"
rm -f "${OUTPUT_FILE}"

append_log "STATUS=SUCCESS | reports refreshed via build_all"
exit 0
