#!/usr/bin/env bash
# Sample one model-server process while a qualification batch runs.
# The final high-water marks are sampled values, not instantaneous hardware peaks.
set -euo pipefail

model_pid="${1:?usage: monitor-qualification.sh MODEL_PID [INTERVAL_SECONDS]}"
interval="${2:-5}"
if [[ ! "$model_pid" =~ ^[0-9]+$ || ! "$interval" =~ ^[1-9][0-9]*$ ]]; then
    echo "MODEL_PID and INTERVAL_SECONDS must be positive integers" >&2
    exit 2
fi
if ! kill -0 "$model_pid" 2>/dev/null; then
    echo "model process $model_pid is not running" >&2
    exit 2
fi
command -v nvidia-smi >/dev/null

peak_gpu_mib=0
peak_rss_kib=0
gpu_samples=0
rss_samples=0
finish() {
    printf 'end_utc=%s model_pid=%s interval_seconds=%s gpu_samples=%s sampled_peak_gpu_mib=%s rss_samples=%s sampled_peak_rss_kib=%s\n' \
        "$(date -u +%FT%TZ)" "$model_pid" "$interval" "$gpu_samples" "$peak_gpu_mib" "$rss_samples" "$peak_rss_kib"
}
trap 'finish; exit 0' INT TERM
printf 'start_utc=%s model_pid=%s interval_seconds=%s\n' "$(date -u +%FT%TZ)" "$model_pid" "$interval"
while kill -0 "$model_pid" 2>/dev/null; do
    gpu_sample="$(nvidia-smi --query-compute-apps=pid,used_gpu_memory --format=csv,noheader,nounits 2>/dev/null | \
        awk -F, -v task_pid="$model_pid" '$1 + 0 == task_pid && $2 ~ /[0-9]/ {sum += $2; count++} END {if (count) print sum}' || true)"
    rss_sample="$(ps -p "$model_pid" -o rss= 2>/dev/null | tr -d '[:space:]' || true)"
    if [[ "$gpu_sample" =~ ^[0-9]+$ ]]; then
        ((gpu_samples+=1))
        if ((gpu_sample > peak_gpu_mib)); then peak_gpu_mib="$gpu_sample"; fi
    fi
    if [[ "$rss_sample" =~ ^[0-9]+$ ]]; then
        ((rss_samples+=1))
        if ((rss_sample > peak_rss_kib)); then peak_rss_kib="$rss_sample"; fi
    fi
    sleep "$interval"
done
finish
