# MadScience Experiments

A classroom-friendly agentic demo that coordinates three specialized agents:

- Scientist Agent: turns a research goal into a classroom experiment proposal.
- Lab Safety Officer Agent: reviews hazards and can approve, modify, or reject.
- Budget Analyst Agent: reviews entered cost against budget policy.

The demo uses a small Python API so the browser can call the agent orchestrator without exposing server-side logic.

## Local Run

Create a local `.env` file with your OpenAI key before expecting automatic safety approval:

```text
OPENAI_API_KEY=replace-with-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
```

The `.env` file is ignored by git. For Vercel, add the same variables in the project environment settings.

```bash
python3 server.py
```

Then open:

```text
http://127.0.0.1:4173/index.html
```

## Python Agent Code

The agent and orchestrator logic lives in:

- `madscience_agents.py`: Scientist, Safety Officer, Budget Analyst, logic check, and final decision rules
- `api/orchestrate.py`: Vercel Python API endpoint used by the browser app
- `server.py`: local Python server for running the app and API together
- `rag_docs/rejection_criteria.txt`: local RAG-style criteria file for rejections, modifications, and HITL review scenarios

`madscience_agents.py` is organized in the same teaching style as the course examples:

- input guardrails
- RAG-backed rejection criteria
- LLM safety sanity check after RAG criteria are cleared
- tool guardrail for the budget review tool
- human-in-the-loop approval scenarios
- handoff-style routing to specialist agents

The presentation deck is available at:

```text
http://127.0.0.1:4173/slides.html
```

## Policies

Budget defaults:

- $25 or less: approve
- $26 to $99: modify
- $100 or more: reject

Presenters can change the budget thresholds in the UI before running the agents.

Safety:

- RAG criteria clear + LLM safety sanity check approves: approve
- Minor classroom hazards: modify
- Hazardous materials, hazardous chemicals, biological agents, explosives, high voltage, high heat, illegal, or regulated activity: reject
- If the OpenAI key is missing or the LLM check fails: modify and require teacher review before classroom use
