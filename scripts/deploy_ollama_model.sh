#!/usr/bin/env bash
set -euo pipefail

# deploy_ollama_model.sh
# Usage: deploy_ollama_model.sh --hosts "user@host1 user@host2" --model-path /abs/path/to/HELVETE-3B --model-name HELVETE-3B --key ~/.ssh/id_ed25519 --dry-run

print_usage(){
  cat <<EOF
Usage: $0 --hosts "user@host1 user@host2" --model-path /abs/path/to/HELVETE-3B --model-name HELVETE-3B [--key /path/to/key] [--no-restart]

This script copies a local model directory (GGUF/safetensors etc.) to remote hosts and installs it under ~/.ollama/models/<model-name>.
It will not automatically install Ollama. If Ollama is missing on a host it will print a helpful message and skip that host.

Options:
  --hosts       Space-separated list of ssh targets in the form user@host (required)
  --model-path  Absolute local path to model directory (required)
  --model-name  Friendly model name to use under ~/.ollama/models (required)
  --key         SSH private key to use (default: use SSH agent or ~/.ssh/id_ed25519)
  --no-restart  Do not restart Ollama service on remote host (default: restart if available)
  --dry-run     Show actions without doing anything

EOF
}

HOSTS=""
MODEL_PATH=""
MODEL_NAME=""
SSH_KEY=""
NO_RESTART=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hosts) HOSTS="$2"; shift 2;;
    --model-path) MODEL_PATH="$2"; shift 2;;
    --model-name) MODEL_NAME="$2"; shift 2;;
    --key) SSH_KEY="$2"; shift 2;;
    --no-restart) NO_RESTART=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) print_usage; exit 0;;
    *) echo "Unknown arg: $1"; print_usage; exit 1;;
  esac
done

if [[ -z "$HOSTS" || -z "$MODEL_PATH" || -z "$MODEL_NAME" ]]; then
  echo "Missing required arguments" >&2
  print_usage
  exit 1
fi

if [[ ! -d "$MODEL_PATH" ]]; then
  echo "Model path not found: $MODEL_PATH" >&2
  exit 1
fi

SSH_OPTS=( -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null )
if [[ -n "$SSH_KEY" ]]; then
  SSH_OPTS+=( -i "$SSH_KEY" )
fi

run_ssh(){
  local target="$1"; shift
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: ssh ${SSH_OPTS[*]} ${target} -- $*"
  else
    ssh "${SSH_OPTS[@]}" "$target" -- "$@"
  fi
}

run_scp_dir(){
  local src_dir="$1"; local target="$2"; local dest="$3"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: rsync -a -e 'ssh ${SSH_OPTS[*]}' $src_dir $target:$dest"
  else
    # NOTE: intentionally DO NOT enable -z (compression) for model transfers.
    # Large model files are not compressed between nodes per project policy.
    rsync -a -e "ssh ${SSH_OPTS[*]}" --delete "$src_dir/" "$target:$dest/"
  fi
}

for t in $HOSTS; do
  echo "--- Processing host: $t ---"

  # Basic connectivity
  if [[ $DRY_RUN -eq 0 ]]; then
    if ! run_ssh "$t" echo ok >/dev/null 2>&1; then
      echo "ERROR: SSH to $t failed - skipping"
      continue
    fi
  else
    echo "DRY-RUN: checking SSH connectivity to $t"
  fi

  # Check Ollama
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: check for 'ollama' on $t"
  else
    if ! run_ssh "$t" "command -v ollama >/dev/null 2>&1"; then
      echo "ollama not found on $t - if you want me to install Ollama automatically, confirm and I'll attempt it (requires root/internet). Skipping this host for now."
      continue
    fi
  fi

  REMOTE_MODEL_DIR="~/.ollama/models/$MODEL_NAME"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: creating remote model dir $REMOTE_MODEL_DIR on $t"
  else
    run_ssh "$t" "mkdir -p $REMOTE_MODEL_DIR"
  fi

  # Copy model files
  echo "Copying model files to $t:$REMOTE_MODEL_DIR"
  run_scp_dir "$MODEL_PATH" "$t" "$REMOTE_MODEL_DIR"

  # (Optional) attempt to restart ollama service if present and allowed
  if [[ $NO_RESTART -eq 0 ]]; then
    echo "Attempting to restart ollama service on $t (if available)"
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "DRY-RUN: ssh ${SSH_OPTS[*]} $t 'echo 1 | sudo -S systemctl restart ollama || true'"
    else
      # Try restart gracefully, ignore failure
      run_ssh "$t" "if systemctl --version >/dev/null 2>&1; then echo 'req sudo' | true; sudo -n systemctl restart ollama 2>/dev/null || true; fi"
    fi
  fi

  # Validate by listing models
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "DRY-RUN: ssh ${SSH_OPTS[*]} $t 'ollama list'"
  else
    echo "Checking 'ollama list' on $t"
    run_ssh "$t" "ollama list || true"
  fi
  echo "--- Done $t ---\n"
done

echo "All hosts processed (dry-run=$DRY_RUN)."
