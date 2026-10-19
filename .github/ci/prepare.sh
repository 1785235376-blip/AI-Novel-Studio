#!/usr/bin/env bash
set -euo pipefail
# Only tracked files at the actual checked-out SHA. Test-generated files, settings,
# runtime state and home/cache directories all stay inside the runner's temp tree.
sandbox="$(mktemp -d "$RUNNER_TEMP/novel-ci-$1.XXXXXX")"
project="$sandbox/project"
receipts="$sandbox/receipts"
mkdir -p "$project" "$receipts" "$sandbox"/{home,config,cache,data,state,tmp,appdata,localappdata}
git archive HEAD | tar -x -C "$project"
{
  printf 'checked_out_sha=%s\n' "$(git rev-parse HEAD)"
  printf 'event_sha=%s\n' "$GITHUB_SHA"
  printf 'run_url=%s/%s/actions/runs/%s\n' "$GITHUB_SERVER_URL" "$GITHUB_REPOSITORY" "$GITHUB_RUN_ID"
  printf 'job=%s\n' "$1"
  printf 'platform=Linux; native Windows host/AppContainer/installer=NOT RUN\n'
} > "$receipts/revision.txt"
{
  echo "CI_SANDBOX=$sandbox"
  echo "CI_PROJECT=$project"
  echo "CI_RECEIPTS=$receipts"
  echo "HOME=$sandbox/home"
  echo "USERPROFILE=$sandbox/home"
  echo "APPDATA=$sandbox/appdata"
  echo "LOCALAPPDATA=$sandbox/localappdata"
  echo "XDG_CONFIG_HOME=$sandbox/config"
  echo "XDG_CACHE_HOME=$sandbox/cache"
  echo "XDG_DATA_HOME=$sandbox/data"
  echo "XDG_STATE_HOME=$sandbox/state"
  echo "TMPDIR=$sandbox/tmp"
  echo "TMP=$sandbox/tmp"
  echo "TEMP=$sandbox/tmp"
  echo "PROJECT_ROOT=$project"
  echo "NOVEL_DATA_PATH=$sandbox/data/novels"
  echo "BACKUP_PATH=$sandbox/data/backups"
  echo "DATABASE_BACKUP_PATH=$sandbox/data/database-backups"
  echo "KNOWLEDGE_SOURCE_PATH=$sandbox/data/novels"
} >> "$GITHUB_ENV"
