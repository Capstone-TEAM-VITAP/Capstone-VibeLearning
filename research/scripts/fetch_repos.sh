#!/usr/bin/env bash
# Re-create research/data/repos at the pinned commits in repos.json.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/repos
node -e '
const r=require("./repos.json");
for (const n of Object.keys(r.shas)) console.log(n, r.urls[n], r.shas[n]);
' | while read -r name url sha; do
  [ -d "data/repos/$name/.git" ] || git clone -q "$url.git" "data/repos/$name"
  git -C "data/repos/$name" checkout -q "$sha"
done
