# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langchain>=1.0",
#   "langchain-mcp-adapters>=0.1",
#   "langchain-openai",
#   "langchain-anthropic",
#   "langchain-ibm",
#   "python-dotenv",
# ]
# ///
"""Load a VAKRA MCP server on Code Engine, call its tools, and let a LangChain agent use them.

  uv run vakra_agent.py --list                                   # list tools
  uv run vakra_agent.py --call get_highest_free_meal_ratio '{"county_name": "Alameda"}'
  uv run vakra_agent.py "Which county has the highest free meal ratio, Alameda or Fresno?"
  uv run vakra_agent.py --cap 3 --domain movie "..."             # other capability / MCP_DOMAIN
  MCP_DOMAIN=superhero uv run vakra_agent.py --list              # or set MCP_DOMAIN like the repo does

LLM_PROVIDER picks the model (see README.md):
  rits     RITS_API_KEY, RITS_BASE_URL, MODEL (e.g. google/gemma-4-31B-it)
  watsonx  WATSONX_APIKEY, WATSONX_PROJECT_ID, WATSONX_URL, MODEL (e.g. openai/gpt-oss-120b)
  other    MODEL is any langchain init_chat_model id, e.g. openai:gpt-4.1 (the default)
"""
import argparse
import asyncio
import json
import os
import re

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BASE = "https://vakra-cap{cap}.1gxwxi8kos9y.us-east.codeengine.appdomain.cloud/mcp/{domain}"

DEFAULT_QUESTIONS = [
    "What is the highest free meal ratio for K-12 students in Alameda county?",
    "List the zip codes of charter schools in the Fresno County Office of Education district.",
]


def make_llm():
    provider = os.environ.get("LLM_PROVIDER", "").lower()
    model = os.environ.get("MODEL")
    if provider == "rits":
        from langchain_openai import ChatOpenAI

        # RITS authenticates with a RITS_API_KEY header, not Authorization: Bearer.
        return ChatOpenAI(
            model=model or "google/gemma-4-31B-it",
            base_url=os.environ.get(
                "RITS_BASE_URL",
                "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com/google-gemma-4-31b-it-a100/v1",
            ),
            api_key="dummy",
            default_headers={"RITS_API_KEY": os.environ["RITS_API_KEY"]},
            temperature=0,
        )
    if provider == "watsonx":
        import warnings

        from langchain_ibm import ChatWatsonx

        warnings.filterwarnings("ignore", module="ibm_watsonx_ai")  # license / max_tokens notices
        return ChatWatsonx(
            model_id=model or "openai/gpt-oss-120b",
            url=os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
            apikey=os.environ["WATSONX_APIKEY"],
            project_id=os.environ["WATSONX_PROJECT_ID"],
            temperature=0,
            max_tokens=4096,
        )
    return init_chat_model(model or "openai:gpt-4.1", temperature=0)


def shortlist(tools, question, limit):
    """Keep the `limit` tools whose name/description share the most words with the question."""
    if len(tools) <= limit:
        return tools
    words = lambda s: set(re.findall(r"[a-z0-9]+", s.lower().replace("_", " ")))
    q = words(question)
    keep = sorted(tools, key=lambda t: -len(q & words(f"{t.name} {t.description}")))[:limit]
    print(f"   ({len(tools)} tools, sending the {limit} that best match the question)")
    return keep


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="*", help="questions for the agent (default: a couple of samples)")
    p.add_argument("--cap", type=int, default=2, help="capability 1-4 (default 2: dashboard APIs)")
    p.add_argument("--domain", default=os.environ.get("MCP_DOMAIN", "california_schools"),
                   help="VAKRA MCP_DOMAIN; the CE bridge takes it from the /mcp/<domain> path")
    p.add_argument("--max-tools", type=int, default=int(os.environ.get("MAX_TOOLS", 128)),
                   help="tools sent to the LLM per question (watsonx rejects more than 128)")
    p.add_argument("--list", action="store_true", help="list tools and exit")
    p.add_argument("--call", nargs=2, metavar=("TOOL", "JSON_ARGS"), help="call one tool directly, no LLM")
    a = p.parse_args()

    url = BASE.format(cap=a.cap, domain=a.domain)
    client = MultiServerMCPClient({"vakra": {"url": url, "transport": "streamable_http"}})
    tools = await client.get_tools()
    if not tools:
        # An unknown MCP_DOMAIN doesn't error, it just serves nothing.
        raise SystemExit(f"0 tools from {url}: is '{a.domain}' a domain of capability {a.cap}? "
                         f"See https://vakra-explorer.1gxwxi8kos9y.us-east.codeengine.appdomain.cloud/api/domains?capability_id={a.cap}")
    print(f"{len(tools)} tools from {url}\n")

    if a.list:
        for t in tools:
            print(f"- {t.name}: {t.description[:110]}")
        return

    if a.call:
        tool = next(t for t in tools if t.name == a.call[0])
        print(await tool.ainvoke(json.loads(a.call[1])))
        return

    llm = make_llm()
    prompt = f"Answer questions about the '{a.domain}' data using only the tools. Be concise."
    for q in a.question or DEFAULT_QUESTIONS:
        print(f"Q: {q}")
        agent = create_agent(llm, shortlist(tools, q, a.max_tools), system_prompt=prompt)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": q}]})
        for m in result["messages"]:
            for tc in getattr(m, "tool_calls", None) or []:
                print(f"   -> {tc['name']}({json.dumps(tc['args'])})")
        print(f"A: {result['messages'][-1].content}\n")


if __name__ == "__main__":
    asyncio.run(main())
