# Provider choices

## Local default: Ollama

Start Ollama and ensure a model is installed. The agent may choose an installed code-capable model after `ollama list`. A larger model and context window may improve flow quality, but both depend on the user's machine. Calls target the local chat endpoint and send only the bounded prompt the agent prepared.

```bash
python3 <skill>/scripts/coddiag.py model \
  --provider ollama --model <installed-model> \
  --prompt evidence-prompt.txt --out candidate.txt
```

The `model` command is optional. The agent can generate `report.json` directly from source inspection. Model output is a draft and still requires validation and semantic audit.

## User-selected OpenAI-compatible endpoint

When the user explicitly requests a remote provider, use an HTTPS base URL ending at the API root (often `/v1`), a model identifier, and `CODDIAG_API_KEY` in the environment. The command posts to `<base-url>/chat/completions` with a bearer token. Do not log the key. Providers may differ in streaming or response fields; this script uses a non-streaming chat completion.

```bash
python3 <skill>/scripts/coddiag.py model \
  --provider openai-compatible --base-url https://example.com/v1 \
  --model <model> --prompt evidence-prompt.txt --out candidate.txt
```

Avoid passing credentials in shell history. Prefer an already-set environment variable. Inspect prompt contents before a remote call. Do not infer consent to upload code from a request to create a diagram.
