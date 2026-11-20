#!/usr/bin/env bash
set -euo pipefail

docker image prune -f

for repository in $(docker image ls --format '{{.Repository}}' | sort -u | grep '^dockship/' || true); do
  tags=$(docker image ls "$repository" --format '{{.CreatedAt}}\t{{.Repository}}:{{.Tag}}' |
    sort -r |
    awk -F '\t' 'NR > 5 {print $2}')
  for tag in $tags; do
    if docker ps --format '{{.Image}}' | grep -Fxq "$tag"; then
      continue
    fi
    docker image rm "$tag" >/dev/null 2>&1 || true
  done
done
