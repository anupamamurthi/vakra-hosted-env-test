#!/usr/bin/env bash
# Example runs, all checked against the live VAKRA servers with watsonx openai/gpt-oss-120b.
# Uses the model in .env. Run all:  ./examples.sh   or copy single lines.
set -e
cd "$(dirname "$0")"

# ── No LLM: load the MCP server and call tools directly ──────────────
uv run vakra_agent.py --list                                        # 89 tools, cap 2 / california_schools
uv run vakra_agent.py --call get_highest_free_meal_ratio '{"county_name": "Alameda"}'

# ── Cap 2: dashboard APIs (one tool per question) ────────────────────
uv run vakra_agent.py --domain california_schools \
  "What is the highest free meal ratio for K-12 students in Alameda county?"
uv run vakra_agent.py --domain superhero "What powers does Captain America have?"

# 152 tools: more than watsonx accepts, so the script sends the 128 best matches.
# Give the race ID: these tools can't map a race name to an ID, so the agent would guess.
# (race 18 = 2008 Australian GP)
uv run vakra_agent.py --domain formula_1 "Who had the fastest Q2 time in race 18?"

# ── Cap 3: multihop (chains tools) ───────────────────────────────────
uv run vakra_agent.py --cap 3 --domain superhero \
  "How many heroes have Super Strength, and how many of those are taller than 200 cm?"

# BPO tools need a requisition ID (05958BR is from the VAKRA test data)
uv run vakra_agent.py --cap 3 --domain bpo \
  "For requisition 05958BR, which sourcing channel made the most hires, and what is its SLA score?"
