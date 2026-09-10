#!/usr/bin/env bash
# Register the local GGUF model set with Ollama under the names config/models.yaml
# expects (sov-local / sov-coder / sov-vision). Run once after `ollama serve` is up.
#
#   MODELS_DIR=~/sovereign-agent/models ./scripts/ollama_setup.sh
#
# GGUF layout expected under MODELS_DIR (quant/name can be anything -- edit below):
#   qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf        + mmproj-F16.gguf   -> sov-local, sov-vision
#   qwen3.5-9b/Qwen3.5-9B-Q4_K_M.gguf                            -> sov-coder
#   (the embedder is pulled from the Ollama registry: `ollama pull nomic-embed-text`)
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-$HOME/sovereign-agent/models}"
CTX="${OLLAMA_NUM_CTX:-8192}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

create() {                       # create <ollama-name> <gguf> [mmproj]
  local name="$1" gguf="$2" mmproj="${3:-}"
  [ -f "$gguf" ] || { echo "SKIP $name: missing $gguf"; return; }
  { echo "FROM $gguf"; [ -n "$mmproj" ] && [ -f "$mmproj" ] && echo "FROM $mmproj"; \
    echo "PARAMETER num_ctx $CTX"; } > "$tmp/Modelfile.$name"
  echo "==> ollama create $name"
  ollama create "$name" -f "$tmp/Modelfile.$name"
}

create sov-local  "$MODELS_DIR/qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf"
create sov-vision "$MODELS_DIR/qwen3.5-4b/Qwen3.5-4B-Q4_K_M.gguf" "$MODELS_DIR/qwen3.5-4b/mmproj-F16.gguf"
create sov-coder  "$MODELS_DIR/qwen3.5-9b/Qwen3.5-9B-Q4_K_M.gguf"

ollama pull nomic-embed-text
echo
echo "Done. Start the API with:"
echo "  MODEL_MODE=ollama OLLAMA_MODEL=sov-local OLLAMA_VISION_MODEL=sov-vision \\"
echo "  OLLAMA_EMBEDDING_MODEL=nomic-embed-text uvicorn app.main:app --port 8080"
