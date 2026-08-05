#!/usr/bin/env bash
set -euo pipefail

case "${IMAGE:?Set IMAGE to a public find-my-timeline GHCR tag}" in
  ghcr.io/heckpiet/find-my-timeline-unraid:*) ;;
  *) echo "Refusing to run an image outside the expected GHCR repository" >&2; exit 2 ;;
esac

host_port="${HOST_PORT:-15010}"
container_name="find-my-timeline-validation-${GITHUB_RUN_ID:-manual}"
data_dir="$(mktemp -d)"

cleanup() {
  docker rm --force "$container_name" >/dev/null 2>&1 || true
  rm -rf -- "$data_dir"
}
trap cleanup EXIT

docker pull "$IMAGE"
docker run --detach --name "$container_name" \
  --publish "127.0.0.1:${host_port}:5000" \
  --volume "$data_dir:/app/data" \
  "$IMAGE" find-my-timeline web --host 0.0.0.0 --port 5000

for attempt in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:${host_port}/health/ready"; then
    curl --fail --silent "http://127.0.0.1:${host_port}/api/system/status"
    exit 0
  fi
  sleep 1
done

docker logs "$container_name"
exit 1
