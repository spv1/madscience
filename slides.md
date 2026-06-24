---
theme: default
title: Applied Agentic AI Course - Student Demo
class: text-center
---

# Applied Agentic AI Course - Student Demo

## MadScience Experiments

by Naresh Raheja

June 25, 2026

---

# Design and Implementation Steps

1. Define the classroom workflow: user goal, Scientist proposal, Safety review, Budget review, final decision, and audit trail.
2. Establish guardrails before automation: reject dangerous experiments, never override reviewer decisions, and explain every rejection or modification.
3. Model each agent as a clear responsibility: Scientist proposes, Safety Officer evaluates risk, Budget Analyst enforces configurable limits.
4. Build the user experience for presentation: simple goal entry, cost input, live agent states, policy cards, and traceable decisions.
5. Publish the implementation: maintain the project in the GitHub repository `spv1/madscience` and deploy the public demo on Vercel.

---

# Iterative Changes

1. Started with fixed demo cases, then generalized proposals so new research goals keep their own topic.
2. Added cost input and configurable budget thresholds: default approve $0-$25, modify $26-$99, reject $100+.
3. Expanded safety guardrails for high voltage, hazardous materials, biological agents, explosives, and high heat.
4. Added an experiment logic check so non-actionable goals, such as planet trajectory studies, are marked invalid before agent review.
5. Tuned classroom safety: ordinary seed growth experiments can approve, while outdoor samples and unknown materials still require controls.
