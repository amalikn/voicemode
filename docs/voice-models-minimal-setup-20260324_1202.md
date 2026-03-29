# Minimal Local Voice Model Setup

This setup creates two local Ollama aliases for safe A/B testing on macOS Apple
Silicon without changing global Ollama configuration.

## What Was Created

- `config/Modelfile.phi4-mini-voice`
- `config/Modelfile.gemma-3-4b-voice`
- `scripts/run-voice-model.sh`
- Ollama alias `phi4-mini-voice`
- Ollama alias `gemma-3-4b-voice`

## Base Models Used

- `phi4-mini-voice` uses `phi4-mini:latest`
  - selected because it is the installed local `phi4-mini` fallback and its
    config blob reports `file_type` `Q4_K_M`
- `gemma-3-4b-voice` uses `gemma3:4b-it-qat`
  - selected because it is installed locally and is the preferred Gemma target
- Ollama version gate for Gemma: `0.18.2`

## Commands Used

```bash
ollama --version
ollama list
ollama create phi4-mini-voice -f config/Modelfile.phi4-mini-voice
ollama create gemma-3-4b-voice -f config/Modelfile.gemma-3-4b-voice
ollama show phi4-mini-voice
ollama show gemma-3-4b-voice
```

## How To Run

```bash
./scripts/run-voice-model.sh phi "Acknowledge in one short sentence."
./scripts/run-voice-model.sh gemma "Summarize this in one short spoken paragraph."
./scripts/run-voice-model.sh phi
./scripts/run-voice-model.sh gemma
```

The aliases themselves set `num_ctx 4096` and `temperature 0.3`, so the helper
script does not need to change global environment variables.

## How To Test

```bash
ollama show phi4-mini-voice
ollama show gemma-3-4b-voice
./scripts/run-voice-model.sh phi "Confirm you avoid guessing live system facts."
./scripts/run-voice-model.sh gemma "Give a short spoken summary of why tools are needed for live facts."
```

## When To Use Which Model

- `phi` -> fast routing, acknowledgments, and short control responses
- `gemma` -> smoother conversational replies and compact spoken summaries

## Rollback

```bash
ollama rm phi4-mini-voice
ollama rm gemma-3-4b-voice
```

## Safety Boundary

- No global Ollama config was changed.
- No `OLLAMA_MODELS` override was created or modified.
- No separate Ollama instance was created.
- No symlinks, hard-links, blob copies, blob moves, or cleanup/prune actions were used.
- No existing model manifests were modified.
- Alias creation adds new alias manifests only; it does not pull, move, or rewrite
  the existing base model blobs.
