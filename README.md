# AI Research Lab Orchestrator

A classroom-friendly agentic demo that coordinates three specialized agents:

- Scientist Agent: turns a research goal into a classroom experiment proposal.
- Lab Safety Officer Agent: reviews hazards and can approve, modify, or reject.
- Budget Analyst Agent: reviews entered cost against budget policy.

The demo is intentionally client-side and dependency-free so it can run locally, on GitHub Pages, or as a static Vercel deployment.

## Local Run

```bash
python3 -m http.server 4173
```

Then open:

```text
http://127.0.0.1:4173/index.html
```

## Policies

Budget:

- $5000 or less: approve
- $5001 to $10000: modify
- More than $10000: reject

Safety:

- Household materials only: approve
- Minor classroom hazards: modify
- Hazardous chemicals, biological agents, explosives, high voltage, high heat, illegal, or regulated activity: reject
