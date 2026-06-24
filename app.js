const form = document.querySelector("#goalForm");
const goalInput = document.querySelector("#researchGoal");
const costInput = document.querySelector("#estimatedCost");
const approveLimitInput = document.querySelector("#approveLimit");
const rejectLimitInput = document.querySelector("#rejectLimit");
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
  budgetApproveText: document.querySelector("#budgetApproveText"),
  budgetModifyText: document.querySelector("#budgetModifyText"),
  budgetRejectText: document.querySelector("#budgetRejectText"),
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

function getBudgetPolicy() {
  const approveMax = normalizeCost(approveLimitInput.value);
  const rejectAt = normalizeCost(rejectLimitInput.value);

  if (approveMax === null || rejectAt === null || rejectAt <= approveMax) {
    return null;
  }

  return { approveMax, rejectAt };
}

function renderBudgetPolicy(policy) {
  if (!policy) {
    outputs.budgetApproveText.innerHTML = "<strong>Approve:</strong> set valid limits";
    outputs.budgetModifyText.innerHTML = "<strong>Modify:</strong> reject-from must be higher";
    outputs.budgetRejectText.innerHTML = "<strong>Reject:</strong> set valid limits";
    return;
  }

  const modifyStart = policy.approveMax + 1;
  const modifyEnd = policy.rejectAt - 1;
  outputs.budgetApproveText.innerHTML = `<strong>Approve:</strong> $${policy.approveMax.toLocaleString()} or less`;
  outputs.budgetModifyText.innerHTML = modifyStart <= modifyEnd
    ? `<strong>Modify:</strong> $${modifyStart.toLocaleString()} to $${modifyEnd.toLocaleString()}`
    : "<strong>Modify:</strong> no middle range";
  outputs.budgetRejectText.innerHTML = `<strong>Reject:</strong> $${policy.rejectAt.toLocaleString()} or more`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function renderDecision(result) {
  const decisionClass = result.finalDecision === "APPROVED"
    ? "approved"
    : result.finalDecision === "REJECTED"
      ? "rejected"
      : result.finalDecision === "MODIFY"
        ? "modify"
        : result.finalDecision === "INVALID GOAL"
          ? "invalid"
          : "human";

  outputs.decisionTitle.textContent = result.finalDecision === "INVALID GOAL"
    ? "Experiment Logic Check: Invalid Goal"
    : `Final Decision: ${result.finalDecision}`;
  outputs.decisionBadge.textContent = result.finalDecision === "INVALID GOAL" ? "INVALID" : result.finalDecision;
  outputs.decisionBadge.className = `decision-badge ${decisionClass}`;
  outputs.decision.className = "";

  const safetyBasis = result.safetyReview
    ? `<div><dt>Safety basis</dt><dd>${escapeHtml(result.safetyReview.reason)}</dd></div>`
    : "";
  const budgetBasis = result.budgetReview
    ? `<div><dt>Budget basis</dt><dd>${escapeHtml(result.budgetReview.reason)}</dd></div>`
    : "";

  outputs.decision.innerHTML = `
    <dl class="detail-list">
      <div><dt>Final Decision</dt><dd><strong>${escapeHtml(result.finalDecision)}</strong></dd></div>
      <div><dt>Explanation</dt><dd>${escapeHtml(result.explanation)}</dd></div>
      ${safetyBasis}
      ${budgetBasis}
    </dl>
  `;
}

function renderInvalidGoal(result) {
  resetState();
  outputs.goal.textContent = result.goal;
  outputs.goal.className = "";
  outputs.decisionTitle.textContent = "Experiment Logic Check: Invalid Goal";
  outputs.decisionBadge.textContent = "INVALID";
  outputs.decisionBadge.className = "decision-badge invalid";
  outputs.proposal.className = "";
  outputs.proposal.innerHTML = `
    <dl class="detail-list">
      <div><dt>Logic check</dt><dd>Not a valid classroom experiment for this workflow.</dd></div>
      <div><dt>Reason</dt><dd>${escapeHtml(result.logicCheck.reason)}</dd></div>
      <div><dt>Try this</dt><dd>${escapeHtml(result.logicCheck.suggestion)}</dd></div>
    </dl>
  `;
  renderDecision(result);
  result.audit.forEach(addAudit);
}

async function callOrchestrator(goal, cost, budgetPolicy) {
  const response = await fetch("/api/orchestrate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ goal, cost, budgetPolicy }),
  });
  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.error || "The Python orchestrator could not process this request.");
  }

  return result;
}

async function runOrchestration(goal, cost, budgetPolicy) {
  resetState();
  outputs.goal.textContent = goal;
  outputs.goal.className = "";
  outputs.decisionTitle.textContent = "Calling Python agents";
  addAudit(`Research goal received: ${goal}`);

  let result;
  try {
    result = await callOrchestrator(goal, cost, budgetPolicy);
  } catch (error) {
    outputs.decisionTitle.textContent = "Python orchestrator unavailable";
    outputs.decisionBadge.textContent = "ERROR";
    outputs.decisionBadge.className = "decision-badge rejected";
    outputs.decision.className = "";
    outputs.decision.innerHTML = `
      <dl class="detail-list">
        <div><dt>Error</dt><dd>${escapeHtml(error.message)}</dd></div>
        <div><dt>Local run</dt><dd>Use python3 server.py so the /api/orchestrate endpoint is available.</dd></div>
      </dl>
    `;
    addAudit(`Python orchestrator error: ${error.message}`);
    return;
  }

  if (result.status === "invalid") {
    renderInvalidGoal(result);
    return;
  }

  addAudit("Experiment logic check passed. The goal is valid for this classroom workflow.");
  setCardState(cards.scientist, "active", "Drafting");
  addAudit("Scientist Agent assigned to create objective, hypothesis, materials, methodology, outcomes, and learning outcomes from the submitted goal.");
  await wait(650);
  renderProposal(result.proposal);
  setCardState(cards.scientist, "done", "Proposal ready");
  addAudit(`Scientist Agent produced proposal with estimated cost $${result.proposal.cost.toLocaleString()} and risk category ${result.proposal.risk}.`);

  setCardState(cards.safety, "active", "Reviewing");
  addAudit("Proposal sent to Lab Safety Officer Agent.");
  await wait(650);
  renderReview(outputs.safety, result.safetyReview);
  setCardState(cards.safety, result.safetyReview.decision === "REJECT" ? "danger" : result.safetyReview.decision === "MODIFY" ? "warning" : "done", result.safetyReview.decision);
  addAudit(`Lab Safety Officer decision: ${result.safetyReview.decision}. ${result.safetyReview.reason}`);

  setCardState(cards.budget, "active", "Reviewing");
  addAudit("Proposal sent to Budget Analyst Agent.");
  await wait(650);
  renderReview(outputs.budget, result.budgetReview);
  setCardState(cards.budget, result.budgetReview.decision === "REJECT" ? "danger" : result.budgetReview.decision === "MODIFY" ? "warning" : "done", result.budgetReview.decision);
  addAudit(`Budget Analyst decision: ${result.budgetReview.decision}. ${result.budgetReview.reason}`);

  await wait(400);
  renderDecision(result);
  addAudit(`Orchestrator final decision: ${result.finalDecision}. ${result.explanation}`);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const goal = normalizeGoal(goalInput.value);
  const cost = normalizeCost(costInput.value);
  const budgetPolicy = getBudgetPolicy();
  renderBudgetPolicy(budgetPolicy);

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

  if (!budgetPolicy) {
    rejectLimitInput.focus();
    addAudit("Run blocked because budget thresholds are invalid. Reject-from must be greater than approve-up-to.");
    return;
  }

  runOrchestration(goal, cost, budgetPolicy);
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

[approveLimitInput, rejectLimitInput].forEach((input) => {
  input.addEventListener("input", () => {
    renderBudgetPolicy(getBudgetPolicy());
  });
});

renderBudgetPolicy(getBudgetPolicy());
