#!/usr/bin/env bash
# Regenerate version.json with the current git commit short SHA and date.
# Run before deploying (or wire into a CI step).
set -euo pipefail

cd "$(dirname "$0")/.."

SHA=$(git rev-parse --short HEAD)
DATE=$(git log -1 --format=%cI)

cat > version.json <<EOF
{
  "commit": "$SHA",
  "date": "$DATE"
}
EOF

echo "version.json updated: commit=$SHA date=$DATE"
