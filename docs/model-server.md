# Set up a model server

Here the *gateway* is simply the OpenAI-compatible address of whatever serves your model.
Ollama or LM Studio on the same computer counts; no separate gateway software is needed. The server
must:

- serve `/v1/chat/completions` and `/v1/models`;
- support tool calling, because Hermes runs the skill's commands through tools;
- give the model a context window large enough for a manuscript and the conversation (64k tokens or
  more is a sensible floor);
- be reachable only from this computer or a private network. Never expose it to the internet:
  Ollama, for example, has no authentication of its own.

Common setups (check your server's documentation for current flags):

| Server | Start | Gateway URL |
|---|---|---|
| Ollama | `ollama pull MODEL`; the app or `ollama serve` runs the server | `http://localhost:11434/v1` |
| LM Studio | load a model and start the local server | `http://127.0.0.1:1234/v1` |
| llama.cpp | `llama-server -m MODEL.gguf --jinja --port 8080` (`--jinja` enables tool calling) | `http://localhost:8080/v1` |
| vLLM | `vllm serve MODEL --enable-auto-tool-choice --tool-call-parser PARSER` (the parser depends on the model family) | `http://localhost:8000/v1` |

Pick a model that supports tool calling (Ollama lists this as the `tools` capability). Check that the
server answers before going further:

```bash
curl http://localhost:11434/v1/models
```

Then select the same server as the main model in the Hermes profile you review from, with a named
provider rather than `auto`. For Ollama:

```yaml
model:
  provider: custom
  base_url: http://localhost:11434/v1
  default: MODEL
```

`hermes model` writes the same thing when you choose a custom or local endpoint. Hermes sends
Ollama the model's full context window automatically; set `model.ollama_num_ctx` to fix a smaller
value, for example to limit memory use. For LM
Studio, `provider: lmstudio` without a `base_url` is fine: Hermes and `creview` both use
`http://127.0.0.1:1234/v1`, or `LM_BASE_URL` if set. `localhost`, `127.0.0.1`, and `::1` count as
the same address. If the server runs on another machine, use that machine's private address
everywhere instead.
