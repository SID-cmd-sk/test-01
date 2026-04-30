#!/usr/bin/env bash
set -euo pipefail

mkdir -p jobs logs samples
[ -f storage/app.db ] || sqlite3 storage/app.db < storage/migrations/0001_init.sql

echo "Bootstrap complete."
