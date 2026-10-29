# Set up a model server

Here the *gateway* is simply the OpenAI-compatible address of whatever serves your model.
Ollama or LM Studio on the same computer counts; no separate gateway software is needed. The server
must:

- serve `/v1/chat/completions` and `/v1/models`;
- support tool calling, because Hermes runs the skill's commands through tools;
- provide an explicitly configured context of at least 65536 tokens for medical support;
- be reachable only from this computer or a private network. Bind to the intended interface and
  enforce host/network access controls; a private address is not authentication.

These are eligibility requirements. They do not establish that a model follows the review
workflow or meets its quality/time targets. Start with the [dedicated profile](install.md), require
`creview hermes doctor --profile NAME --support`, then run the real Hermes module checks in
[the support pilot protocol](support-pilot.md). Formal qualification needs independently approved
medical cases, three paired repetitions, human finding/baseline audits and exact runtime/hardware
evidence. The [legacy scan qualification](deployment.md) and `hermes smoke` do not qualify these
modules. Test context sizes only when actually configured on the server. Do not buy hardware on
the basis of a model name or advertised maximum context alone; the existing workstation evidence
does not establish a portable memory minimum or qualify another server/model.

For medical support, use `creview hermes setup-profile` as documented in the installation guide
instead of copying only a main-model configuration. The managed profile explicitly uses the
`custom` provider and pins compression, title generation, vision and disabled background review
to the same trusted local gateway and allowlisted model. The context value supplied to profile
setup must reflect the real server limit; it does not resize the server. A passing preflight is
not an OS network sandbox or a scientific-quality result.

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

### Legacy/development configuration notes

The following main-model-only examples describe compatibility, not a medical-support profile.
For medical support use the managed setup above; in particular it requires `provider: custom`,
not a different provider alias merely because legacy routing can resolve it.

Select the same server as the main model, with a named provider rather than `auto`. For Ollama:

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
