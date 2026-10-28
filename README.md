# VAKRA MCP demo

A small script that connects to the VAKRA MCP servers running on IBM Code Engine, lists or calls their tools, and lets a LangChain agent answer questions with them. It can use RITS, watsonx or any other LangChain model.

VAKRA benchmark: https://github.com/IBM/vakra

## Requirements

- [uv](https://docs.astral.sh/uv/). The script declares its own dependencies, so `uv run` installs them on the first run.
- For the agent: credentials for one model provider (see [Choose a model](#choose-a-model)). Listing and calling tools needs no credentials.

## Files

| File | What it is |
|---|---|
| `vakra_agent.py` | The script |
| `.env.example` | Settings template for watsonx, RITS or another provider |
| `.env` | Your settings and keys. Gitignored; the script loads it automatically |
| `examples.sh` | Example runs, each checked against the live servers |

## Quick start

```bash
cp .env.example .env      # then fill in one provider
./examples.sh             # or run single commands:

# List the tools for one domain
uv run vakra_agent.py --list

# Call one tool directly, without an LLM
uv run vakra_agent.py --call get_highest_free_meal_ratio '{"county_name": "Alameda"}'

# Ask the agent a question (uses the model set in .env)
uv run vakra_agent.py "What is the highest free meal ratio for K-12 students in Alameda county?"
```

The agent prints each tool call it makes, then its answer. With no question, it asks two sample questions.

## Servers and domains

Each capability is a separate Code Engine app in the `ce-project-routing` project (RIS3 account, us-east). The app serves one MCP endpoint (streamable HTTP) per domain:

```
https://vakra-cap<N>.1gxwxi8kos9y.us-east.codeengine.appdomain.cloud/mcp/<domain>
```

| `--cap` | Capability |
|---|---|
| 1 | Slot-filling: SQL and selection tools |
| 2 | Dashboard APIs: M3 REST / FastAPI tools (the default) |
| 3 | Multihop reasoning: M3 REST, or BPO tools when the domain is `bpo` |
| 4 | Multiturn: M3 REST tools plus a semantic retriever |

The domain plays the role of `MCP_DOMAIN` in the VAKRA repo. Set it with `--domain` or the `MCP_DOMAIN` environment variable; the default is `california_schools`.

```bash
MCP_DOMAIN=superhero uv run vakra_agent.py --list
uv run vakra_agent.py --cap 3 --domain movie "Which movie ...?"
```

Each capability has its own set of domains. A domain that doesn't exist returns 0 tools rather than an error, so the script stops and tells you if that happens. To see the domains for a capability:

```
https://vakra-explorer.1gxwxi8kos9y.us-east.codeengine.appdomain.cloud/api/domains?capability_id=<N>
```

The explorer's home page, https://vakra-explorer.1gxwxi8kos9y.us-east.codeengine.appdomain.cloud, lets you browse and try tools in the browser.

## Choose a model

Set `LLM_PROVIDER`, and optionally `MODEL`, in `.env` or in your shell. Shell variables take precedence over `.env`.

### RITS

```bash
export LLM_PROVIDER=rits
export RITS_API_KEY=...
export RITS_BASE_URL=https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/google-gemma-4-31b-it-a100/v1
export MODEL=google/gemma-4-31B-it
```

- RITS works on the IBM network only (VPN or on-site).
- RITS uses an OpenAI-compatible API, but sends the key in a `RITS_API_KEY` header instead of `Authorization: Bearer`. The script handles this.
- Each model has its own base URL. Copy the base URL and model name for the model you want from the RITS model list. The values above are the defaults if you set only `RITS_API_KEY`.
- The model needs to support tool calling.

### watsonx

```bash
export LLM_PROVIDER=watsonx
export WATSONX_APIKEY=...                          # IBM Cloud API key
export WATSONX_PROJECT_ID=...                      # watsonx.ai project ID
export WATSONX_URL=https://us-south.ml.cloud.ibm.com
export MODEL=openai/gpt-oss-120b
```

- `WATSONX_URL` is the region of your watsonx.ai project. `us-south` is the default.
- `MODEL` is a watsonx model ID that supports tool calling, such as `openai/gpt-oss-120b` (the default) or `meta-llama/llama-3-3-70b-instruct`.
- Uses [`langchain-ibm`](https://python.langchain.com/docs/integrations/chat/ibm_watsonx/) (`ChatWatsonx`).
- watsonx accepts at most 128 tools per request, and some domains have more (`formula_1` has 152). When a domain has more tools than `--max-tools` (default 128), the script sends the ones whose names and descriptions share the most words with the question.

### Other providers

Leave `LLM_PROVIDER` unset. `MODEL` is then any LangChain `init_chat_model` ID:

```bash
export OPENAI_API_KEY=...
export MODEL=openai:gpt-4.1          # the default
# or: export ANTHROPIC_API_KEY=... MODEL=anthropic:claude-sonnet-5
```

For other OpenAI-compatible gateways, such as LiteLLM, also set `OPENAI_BASE_URL`.

## Options

| Option | Default | Meaning |
|---|---|---|
| `question ...` | two samples | One or more questions for the agent |
| `--cap N` | `2` | Capability 1–4 |
| `--domain D` | `$MCP_DOMAIN` or `california_schools` | MCP domain |
| `--max-tools N` | `$MAX_TOOLS` or `128` | Most tools sent to the LLM per question |
| `--list` | | List tools and exit |
| `--call TOOL JSON` | | Call one tool with JSON arguments, no LLM |

## Tips for writing questions

- Some IDs can't be looked up from names: no `formula_1` tool maps a race name to its ID, and every BPO tool needs a requisition ID. Put the ID in the question, for example "race 18" or "requisition 05958BR". Otherwise the agent may guess and answer confidently but wrongly.
- The VAKRA test data (`data/test/` in the repo) has real IDs and questions to try.
