#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

export FAMILYBOX_ROOT="${FAMILYBOX_ROOT:-$project_dir/.familybox}"
export FAMILYBOX_HARDWARE="${FAMILYBOX_HARDWARE:-fake}"
export FAMILYBOX_AUDIO="${FAMILYBOX_AUDIO:-fake}"
export FAMILYBOX_DEV_ENDPOINTS="${FAMILYBOX_DEV_ENDPOINTS:-true}"
export FAMILYBOX_JSON_LOGS="${FAMILYBOX_JSON_LOGS:-false}"

exec uvicorn familybox.main:app --host 127.0.0.1 --port "${FAMILYBOX_WEB_PORT:-8080}" --reload
