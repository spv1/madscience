const form = document.querySelector("#goalForm");
const goalInput = document.querySelector("#researchGoal");
const costInput = document.querySelector("#estimatedCost");
const resetButton = document.querySelector("#resetButton");
const chips = document.querySelectorAll(".chip");
const auditTrail = document.querySelector("#auditTrail");

const outputs = {
  goal: document.querySelector("#goalOutput"),
  proposal: document.querySelector("#proposalOutput"),
  safety: document.querySelector("#safetyOutput"),
  budget: document.querySelector("#budgetOutput"),
  decision: document.querySelector("#decisionOutput"),
  decisionTitle: document.querySelector("#decisionTitle"),
  decisionBadge: document.querySelector("#decisionBadge"),
};

const cards = {
  scientist: document.querySelector("#scientistCard"),
  safety: document.querySelector("#safetyCard"),
  budget: document.querySelector("#budgetCard"),
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function addAudit(message) {
  const item = document.createElement("li");
  item.textContent = `${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })} - ${message}`;
  auditTrail.prepend(item);
}

function setCardState(card, state, label) {
  card.className = `agent-card ${state}`;
  card.querySelector(".status-pill").textContent = label;
}

function resetState() {
  outputs.goal.textContent = "Submit a goal to begin.";
  outputs.goal.className = "placeholder";
  outputs.proposal.textContent = "No proposal yet.";
  outputs.proposal.className = "placeholder";
  outputs.safety.textContent = "No safety review yet.";
  outputs.safety.className = "placeholder";
  outputs.budget.textContent = "No budget review yet.";
  outputs.budget.className = "placeholder";
  outputs.decision.textContent = "Awaiting agent decisions.";
  outputs.decision.className = "placeholder";
  outputs.decisionTitle.textContent = "Ready for a research goal";
  outputs.decisionBadge.textContent = "WAITING";
  outputs.decisionBadge.className = "decision-badge neutral";
  setCardState(cards.scientist, "idle", "Waiting");
  setCardState(cards.safety, "idle", "Waiting");
  setCardState(cards.budget, "idle", "Waiting");
}

function normalizeGoal(goal) {
  return goal.trim().replace(/\s+/g, " ");
}

function normalizeCost(cost) {
  const value = Number(cost);
  return Number.isFinite(value) && value >= 0 ? Math.round(value) : null;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sentenceCase(value) {
  const clean = value.trim();
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

function identifySafetyProfile(goal) {
  const lower = goal.toLowerCase();
  const rejectRules = [
    { pattern: /high[- ]?voltage|electrocution|mains electricity|tesla coil|visible arcs?|power supply/, label: "high voltage" },
    { pattern: /explosive|explosion|detonation|gunpowder|firework|rocket fuel|propellant/, label: "explosives or energetic materials" },
    { pattern: /hazardous (material|substance|chemical)|toxic material|toxic substance|strong acid|strong base|cyanide|mercury|chlorine gas|toxic gas|poison/, label: "hazardous materials or chemicals" },
    { pattern: /pathogen|virus|bacteria|mold|blood|bodily fluid|biological agent|culture unknown microbes/, label: "biological agents" },
    { pattern: /open flame|torch|combustion|burning|boiling oil|high heat|furnace/, label: "high heat" },
    { pattern: /animal testing|human subject|medical treatment|drug|illegal/, label: "regulated or illegal activity" },
  ];
  const modifyRules = [
    { pattern: /warm water|hot water|heat|temperature|yeast|baker'?s yeast|vinegar|baking soda|salt|sugar|caffeine|magnet|sharp|scissors/, label: "minor classroom hazard" },
    { pattern: /plant|seed|soil|water sample|food|allergen|outdoor sample/, label: "materials that need handling controls" },
  ];
  const rejectMatch = rejectRules.find((rule) => rule.pattern.test(lower));
  const modifyMatch = modifyRules.find((rule) => rule.pattern.test(lower));

  if (rejectMatch) return { risk: "hazardous", trigger: rejectMatch.label };
  if (modifyMatch) return { risk: "minor", trigger: modifyMatch.label };
  return { risk: "household", trigger: "household materials only" };
}

function inferStudyType(goal) {
  const lower = goal.toLowerCase();

  if (/plant|seed|soil|water quality|germination|growth/.test(lower)) {
    return {
      variable: "environmental condition",
      measurement: "growth, visible change, or count data",
      materials: ["household containers", "labels", "measuring tool", "observation sheet", "teacher-approved samples"],
    };
  }

  if (/temperature|insulat|heat loss|warm|cool/.test(lower)) {
    return {
      variable: "material or temperature condition",
      measurement: "temperature readings over time",
      materials: ["cups", "thermometer", "timer", "household insulating materials", "data table"],
    };
  }

  if (/light|color|sound|motion|force|friction|magnet/.test(lower)) {
    return {
      variable: "physical condition",
      measurement: "repeatable observations or simple measurements",
      materials: ["classroom-safe test objects", "ruler or timer", "labels", "data table"],
    };
  }

  return {
    variable: "one controlled variable",
    measurement: "repeatable observations and simple measurements",
    materials: ["household or classroom-safe materials", "labels", "measuring tool", "observation sheet"],
  };
}

function inferProposal(goal, cost) {
  const safetyProfile = identifySafetyProfile(goal);
  const studyType = inferStudyType(goal);
  const objectiveGoal = sentenceCase(goal.replace(/[.?!]+$/, ""));
  const hazardous = safetyProfile.risk === "hazardous";

  return {
    objective: objectiveGoal,
    hypothesis: `If students vary ${studyType.variable}, then ${studyType.measurement} will show whether the goal is supported by evidence.`,
    materials: hazardous
      ? ["Materials withheld pending safety review", "non-hazardous simulation or teacher-approved substitute", "observation sheet"]
      : studyType.materials,
    methodology: hazardous
      ? "Do not run the proposed activity as written. Convert the goal into a non-hazardous simulation, demonstration video analysis, or teacher-approved substitute before any classroom use."
      : "Set up a small controlled comparison, change one variable at a time, collect repeated observations, and summarize results in a table or chart.",
    outcomes: "Students practice hypothesis formation, controls, measurement, evidence-based explanation, and responsible review of safety and resource constraints.",
    cost,
    risk: safetyProfile.risk,
    safetyTrigger: safetyProfile.trigger,
  };
}

function reviewSafety(proposal) {
  if (proposal.risk === "hazardous") {
    return {
      decision: "REJECT",
      reason: `The proposal appears to involve ${proposal.safetyTrigger}. Classroom instructions are not allowed for that risk category.`,
      requirements: ["Replace with a non-hazardous simulation, video analysis, or teacher-approved substitute."],
    };
  }

  if (proposal.risk === "minor") {
    return {
      decision: "MODIFY",
      reason: `The proposal is mostly classroom-safe but includes ${proposal.safetyTrigger}, so it needs tighter controls.`,
      requirements: ["Add teacher supervision, small quantities, cleanup, labeling, and handwashing or handling procedures as appropriate."],
    };
  }

  return {
    decision: "APPROVE",
    reason: "Materials are household-level and the procedure avoids dangerous heat, voltage, chemicals, and biological agents.",
    requirements: ["Keep quantities small and supervise measurements."],
  };
}

function reviewBudget(proposal) {
  if (proposal.cost > 10000) {
    return {
      decision: "REJECT",
      reason: `Estimated cost is $${proposal.cost.toLocaleString()}, which exceeds the $10000 rejection threshold.`,
      requirements: ["Choose a lower-cost research design."],
    };
  }

  if (proposal.cost > 5000) {
    return {
      decision: "MODIFY",
      reason: `Estimated cost is $${proposal.cost.toLocaleString()}, which requires modification under the budget policy.`,
      requirements: ["Reduce equipment, reuse existing materials, or narrow the scope."],
    };
  }

  return {
    decision: "APPROVE",
    reason: `Estimated cost is $${proposal.cost.toLocaleString()}, within the $5000 approval threshold.`,
    requirements: ["Track actual expenses against the estimate."],
  };
}

function evaluateReviews(safety, budget) {
  const decisions = [safety.decision, budget.decision];

  if (decisions.includes("REJECT")) {
    return {
      decision: "REJECTED",
      explanation: "At least one required reviewer rejected the proposal, so the orchestrator cannot approve or modify it.",
    };
  }

  if (decisions.includes("MODIFY")) {
    return {
      decision: "MODIFY",
      explanation: "At least one required reviewer requested changes. Required changes must be addressed before approval.",
    };
  }

  if (new Set(decisions).size > 1) {
    return {
      decision: "HUMAN REVIEW",
      explanation: "Reviewer decisions conflict in a way the policy cannot safely resolve automatically.",
    };
  }

  return {
    decision: "APPROVED",
    explanation: "Both required reviewers approved the proposal.",
  };
}

function renderProposal(proposal) {
  outputs.proposal.className = "";
  outputs.proposal.innerHTML = `
    <dl class="detail-list">
      <div><dt>Objective</dt><dd>${escapeHtml(proposal.objective)}</dd></div>
      <div><dt>Hypothesis</dt><dd>${escapeHtml(proposal.hypothesis)}</dd></div>
      <div><dt>Materials</dt><dd>${escapeHtml(proposal.materials.join(", "))}</dd></div>
      <div><dt>Methodology</dt><dd>${escapeHtml(proposal.methodology)}</dd></div>
      <div><dt>Expected learning outcomes</dt><dd>${escapeHtml(proposal.outcomes)}</dd></div>
      <div><dt>Estimated cost</dt><dd>$${proposal.cost.toLocaleString()}</dd></div>
    </dl>
  `;
}

function renderReview(target, review) {
  target.className = "";
  target.innerHTML = `
    <div class="review-box">
      <span class="review-decision ${review.decision.toLowerCase()}">${escapeHtml(review.decision)}</span>
      <p>${escapeHtml(review.reason)}</p>
      <dl class="detail-list">
        <div><dt>Required action</dt><dd>${escapeHtml(review.requirements.join(" "))}</dd></div>
      </dl>
    </div>
  `;
}

function renderDecision(result, safety, budget) {
  const decisionClass = result.decision === "APPROVED"
    ? "approved"
    : result.decision === "REJECTED"
      ? "rejected"
      : result.decision === "MODIFY"
        ? "modify"
        : "human";

  outputs.decisionTitle.textContent = `Final Decision: ${result.decision}`;
  outputs.decisionBadge.textContent = result.decision;
  outputs.decisionBadge.className = `decision-badge ${decisionClass}`;
  outputs.decision.className = "";
  outputs.decision.innerHTML = `
    <dl class="detail-list">
      <div><dt>Final Decision</dt><dd><strong>${result.decision}</strong></dd></div>
      <div><dt>Explanation</dt><dd>${escapeHtml(result.explanation)}</dd></div>
      <div><dt>Safety basis</dt><dd>${escapeHtml(safety.reason)}</dd></div>
      <div><dt>Budget basis</dt><dd>${escapeHtml(budget.reason)}</dd></div>
    </dl>
  `;
}

async function runOrchestration(goal, cost) {
  resetState();
  outputs.goal.textContent = goal;
  outputs.goal.className = "";
  outputs.decisionTitle.textContent = "Agents are evaluating the proposal";
  addAudit(`Research goal received: ${goal}`);

  setCardState(cards.scientist, "active", "Drafting");
  addAudit("Scientist Agent assigned to create objective, hypothesis, materials, methodology, outcomes, and learning outcomes from the submitted goal.");
  await wait(650);
  const proposal = inferProposal(goal, cost);
  renderProposal(proposal);
  setCardState(cards.scientist, "done", "Proposal ready");
  addAudit(`Scientist Agent produced proposal with estimated cost $${proposal.cost.toLocaleString()} and risk category ${proposal.risk}.`);

  setCardState(cards.safety, "active", "Reviewing");
  addAudit("Proposal sent to Lab Safety Officer Agent.");
  await wait(650);
  const safety = reviewSafety(proposal);
  renderReview(outputs.safety, safety);
  setCardState(cards.safety, safety.decision === "REJECT" ? "danger" : safety.decision === "MODIFY" ? "warning" : "done", safety.decision);
  addAudit(`Lab Safety Officer decision: ${safety.decision}. ${safety.reason}`);

  setCardState(cards.budget, "active", "Reviewing");
  addAudit("Proposal sent to Budget Analyst Agent.");
  await wait(650);
  const budget = reviewBudget(proposal);
  renderReview(outputs.budget, budget);
  setCardState(cards.budget, budget.decision === "REJECT" ? "danger" : budget.decision === "MODIFY" ? "warning" : "done", budget.decision);
  addAudit(`Budget Analyst decision: ${budget.decision}. ${budget.reason}`);

  await wait(400);
  const result = evaluateReviews(safety, budget);
  renderDecision(result, safety, budget);
  addAudit(`Orchestrator final decision: ${result.decision}. ${result.explanation}`);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const goal = normalizeGoal(goalInput.value);
  const cost = normalizeCost(costInput.value);

  if (!goal) {
    goalInput.focus();
    addAudit("Run blocked because no research goal was provided.");
    return;
  }

  if (cost === null) {
    costInput.focus();
    addAudit("Run blocked because no valid estimated cost was provided.");
    return;
  }

  runOrchestration(goal, cost);
});

resetButton.addEventListener("click", () => {
  goalInput.value = "";
  costInput.value = "";
  resetState();
  addAudit("Demo reset by presenter.");
});

chips.forEach((chip) => {
  chip.addEventListener("click", () => {
    goalInput.value = chip.dataset.goal;
    costInput.value = chip.dataset.cost;
    goalInput.focus();
  });
});
