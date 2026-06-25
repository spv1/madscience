"""MadScience Experiments agentic demo.

This file mirrors the beginner-friendly structure used in the course examples:

1. Input guardrails block invalid classroom experiment requests.
2. A local RAG file provides rejection, modification, and HITL criteria.
3. Tool guardrails protect budget decisions before the budget tool runs.
4. HITL approval scenarios escalate proposals that need a human reviewer.
5. Handoff-style functions route work to the Scientist, Safety Officer, and Budget Analyst.

Run locally through the browser app:
    python3 server.py

Try:
    "Design a safe classroom experiment that shows how water quality affects radish seed growth."
    "study the trajectory of planets"
    "Explore whether a new hazardous material keeps a battery running much longer"
    "Compare how student heart rates change after exercise."
"""

from __future__ import annotations

import json
import os
import re
import hashlib
from http.client import IncompleteRead, RemoteDisconnected
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RAG_FOLDER = Path(__file__).parent / "rag_docs"
REJECTION_CRITERIA_FILE = RAG_FOLDER / "rejection_criteria.txt"
ENV_FILE = Path(__file__).parent / ".env"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY_ENV_NAMES = (
    "OPENAI_API_KEY",
    "OPENAI_KEY",
    "OPEN_AI_API_KEY",
)


# ============================================================
# Shared data structures
# ============================================================
# These classes keep the orchestration output consistent for the browser UI.

@dataclass
class CriteriaRule:
    decision: str
    label: str
    pattern: str
    reason: str
    requirement: str


# ============================================================
# Basic normalization helpers
# ============================================================
# These helpers replace the small bits of cleanup that would normally happen
# before an agent run starts.

def normalize_goal(goal: Any) -> str:
    """Clean up user-entered research goals."""
    return re.sub(r"\s+", " ", str(goal or "").strip())


def normalize_cost(cost: Any) -> int | None:
    """Convert user-entered costs and thresholds into whole-dollar values."""
    try:
        value = float(cost)
    except (TypeError, ValueError):
        return None
    return round(value) if value >= 0 else None


def normalize_budget_policy(policy: dict[str, Any] | None) -> dict[str, int] | None:
    """Validate the presenter's budget thresholds."""
    policy = policy or {}
    approve_max = normalize_cost(policy.get("approveMax"))
    reject_at = normalize_cost(policy.get("rejectAt"))

    if approve_max is None or reject_at is None or reject_at <= approve_max:
        return None

    return {"approveMax": approve_max, "rejectAt": reject_at}


def sentence_case(value: Any) -> str:
    """Capitalize the first character without changing the rest of the text."""
    clean = str(value or "").strip()
    return clean[:1].upper() + clean[1:]


def load_local_env(path: Path = ENV_FILE) -> None:
    """Load simple KEY=value pairs from .env for local classroom runs."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()


def get_openai_api_key() -> tuple[str, str | None]:
    """Return the first configured OpenAI key and the env var name that supplied it."""
    for name in OPENAI_API_KEY_ENV_NAMES:
        value = os.environ.get(name, "").strip()
        if value and not value.startswith("replace-with"):
            return value, name

    return "", None


def text_contains_any(text: str, terms: list[str]) -> bool:
    """Return True when any term appears as plain text."""
    return any(term in text for term in terms)


def mitigation_controls_present(goal: str, proposal: dict[str, Any], modify_rule: CriteriaRule) -> bool:
    """Detect whether the RAG-required mitigation categories are already included."""
    combined = " ".join(
        [
            goal,
            str(proposal.get("objective", "")),
            " ".join(map(str, proposal.get("materials", []))),
            str(proposal.get("methodology", "")),
        ]
    ).lower()

    if modify_rule.label == "minor classroom hazard":
        checks = [
            ["teacher supervision", "supervised", "teacher-approved", "teacher approved"],
            ["small quantities", "small quantity", "small amounts", "small amount"],
            ["cleanup", "clean up", "clean-up"],
            ["label", "labels", "labeling", "labelled"],
            ["handling", "safe handling", "handle safely"],
        ]
        return all(text_contains_any(combined, terms) for terms in checks)

    if modify_rule.label == "classroom water quality sample":
        checks = [
            ["teacher-approved", "teacher approved", "teacher supervision", "supervised"],
            ["non-hazardous", "nonhazardous", "safe water", "classroom-safe"],
            ["small quantities", "small quantity", "small amounts", "small amount"],
            ["label", "labels", "labeling", "labelled"],
            ["cleanup", "clean up", "clean-up"],
        ]
        return all(text_contains_any(combined, terms) for terms in checks)

    if modify_rule.label == "outdoor or unknown sample":
        checks = [
            ["sealed container", "sealed containers", "closed container", "closed containers"],
            ["teacher handling", "teacher handles", "teacher supervision", "supervised"],
            ["gloves", "glove"],
            ["cleanup", "clean up", "clean-up"],
        ]
        return all(text_contains_any(combined, terms) for terms in checks)

    if modify_rule.label == "allergy or food handling":
        checks = [
            ["avoid allergens", "no allergens", "allergen-free", "allergy policy"],
            ["label", "labels", "labeling", "labelled"],
            ["classroom allergy policy", "confirm allergy", "check allergy"],
        ]
        return all(text_contains_any(combined, terms) for terms in checks)

    return False


def student_measurement_controls_present(goal: str, proposal: dict[str, Any]) -> bool:
    """Detect when a student-measurement HITL case already includes basic safeguards."""
    combined = " ".join(
        [
            goal,
            str(proposal.get("objective", "")),
            str(proposal.get("methodology", "")),
        ]
    ).lower()

    has_student_measurement = text_contains_any(
        combined,
        ["heart rate", "heart rates", "pulse", "breathing rate"],
    )
    has_light_activity = text_contains_any(
        combined,
        ["light exercise", "gentle exercise", "walking", "one minute", "short activity", "resting"],
    )
    has_supervision = text_contains_any(
        combined,
        ["teacher supervision", "supervised", "teacher-approved", "teacher approved"],
    )
    has_consent = text_contains_any(
        combined,
        ["consent", "opt out", "voluntary"],
    )
    has_privacy = text_contains_any(
        combined,
        ["anonymous", "anonymized", "privacy", "no public sharing", "no individual data"],
    )

    return all(
        [
            has_student_measurement,
            has_light_activity,
            has_supervision,
            has_consent,
            has_privacy,
        ]
    )


# ============================================================
# Input guardrails
# ============================================================
# 1. Input guardrails run before any specialist agent is called.
# 2. They block missing, malformed, or non-experiment requests.
# 3. A blocked input never reaches Scientist, Safety, or Budget review.

def required_fields_guardrail(goal: str, cost: int | None, policy: dict[str, int] | None) -> dict[str, Any]:
    """Block runs that do not have the minimum fields needed for review."""
    if not goal:
        return {
            "valid": False,
            "reason": "A research goal is required.",
            "suggestion": "Enter a testable classroom experiment goal.",
        }

    if cost is None:
        return {
            "valid": False,
            "reason": "A valid estimated cost is required.",
            "suggestion": "Enter a whole-dollar estimated cost.",
        }

    if policy is None:
        return {
            "valid": False,
            "reason": "Budget thresholds are invalid. Reject-from must be greater than approve-up-to.",
            "suggestion": "Set the reject threshold higher than the approve threshold.",
        }

    return {"valid": True, "reason": "Required fields are present."}


def experiment_logic_guardrail(goal: str) -> dict[str, Any]:
    """Block requests that are not actionable classroom experiments."""
    lower = goal.lower()
    impossible_scale = re.search(
        r"planet|orbit|solar system|galaxy|star|black hole|comet|asteroid",
        lower,
    )
    observation_only = re.search(
        r"trajectory|formation|history|origin|evolution|location|distance|mass|age",
        lower,
    )
    has_experiment_signal = re.search(
        r"test|compare|measure|investigate|explore|evaluate|observe|vary|effect|affect|impact|change|longer|faster|slower|growth|temperature|distance|absorb|retain",
        lower,
    )

    if impossible_scale and observation_only:
        return {
            "valid": False,
            "reason": "This goal is better framed as astronomy observation or modeling, not a classroom experiment with a manipulable variable.",
            "suggestion": "Reframe it as a model-based experiment, such as testing how starting angle or launch speed affects the path of a marble or ball in a classroom-scale orbit model.",
        }

    if not has_experiment_signal:
        return {
            "valid": False,
            "reason": "The goal does not describe a measurable comparison, variable, or outcome the agents can evaluate as an experiment.",
            "suggestion": "Rewrite it as a testable question with one changed variable and one measurable result.",
        }

    return {
        "valid": True,
        "reason": "The goal can be reviewed as a testable classroom experiment.",
    }


# ============================================================
# RAG criteria loader
# ============================================================
# 1. The safety and HITL criteria live in rag_docs/rejection_criteria.txt.
# 2. Each rule is pipe-delimited so teachers can edit it without touching code.
# 3. The Safety Officer retrieves the first matching rule for the goal.

def load_rejection_criteria(path: Path = REJECTION_CRITERIA_FILE) -> list[CriteriaRule]:
    """Load reject, modify, and HITL rules from a local RAG-style text file."""
    rules: list[CriteriaRule] = []
    text = path.read_text(encoding="utf-8")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in line.split(" | ")]
        if len(parts) != 5:
            continue

        decision, label, pattern, reason, requirement = parts
        rules.append(
            CriteriaRule(
                decision=decision.upper(),
                label=label,
                pattern=pattern,
                reason=reason,
                requirement=requirement,
            )
        )

    if not rules:
        raise RuntimeError(f"Add at least one criteria rule to {path}.")

    return rules


def retrieve_criteria(goal: str, decision: str | None = None) -> CriteriaRule | None:
    """Retrieve the first local criteria rule that matches the research goal."""
    lower = goal.lower()

    for rule in load_rejection_criteria():
        if decision and rule.decision != decision.upper():
            continue
        if re.search(rule.pattern, lower):
            return rule

    return None


# ============================================================
# Tool guardrail
# ============================================================
# 1. The Budget Analyst uses a budget review "tool."
# 2. The guardrail checks threshold validity before the tool runs.
# 3. Bad threshold settings are blocked before a decision is fabricated.

def budget_tool_guardrail(cost: int, policy: dict[str, int]) -> dict[str, Any]:
    """Protect the budget review tool from invalid inputs."""
    if cost < 0:
        return {
            "allowed": False,
            "reason": "Estimated cost cannot be negative.",
        }

    if policy["rejectAt"] <= policy["approveMax"]:
        return {
            "allowed": False,
            "reason": "Reject-from must be greater than approve-up-to.",
        }

    return {"allowed": True, "reason": "Budget tool input is valid."}


def budget_review_tool(cost: int, policy: dict[str, int]) -> dict[str, Any]:
    """Review proposal cost using presenter-configurable thresholds."""
    guardrail = budget_tool_guardrail(cost, policy)
    if not guardrail["allowed"]:
        return {
            "decision": "REJECT",
            "reason": guardrail["reason"],
            "requirements": ["Fix the budget settings before running the review."],
        }

    if cost >= policy["rejectAt"]:
        return {
            "decision": "REJECT",
            "reason": f"Estimated cost is ${cost:,}, which meets or exceeds the ${policy['rejectAt']:,} rejection threshold.",
            "requirements": ["Choose a lower-cost research design."],
        }

    if cost > policy["approveMax"]:
        return {
            "decision": "MODIFY",
            "reason": f"Estimated cost is ${cost:,}, above the ${policy['approveMax']:,} approval limit and below the ${policy['rejectAt']:,} rejection threshold.",
            "requirements": [
                "Reduce equipment, reuse existing materials, or narrow the scope."
            ],
        }

    return {
        "decision": "APPROVE",
        "reason": f"Estimated cost is ${cost:,}, within the ${policy['approveMax']:,} approval threshold.",
        "requirements": ["Track actual expenses against the estimate."],
    }


# ============================================================
# HITL approval
# ============================================================
# 1. HITL approval is used when the demo should not auto-approve.
# 2. These scenarios are not always rejected; they need human judgment.
# 3. The UI marks them HUMAN REVIEW so a teacher or administrator can decide.

def human_approval_check(goal: str, proposal: dict[str, Any]) -> dict[str, Any]:
    """Return a pending approval if the proposal needs human review."""
    hitl_rule = retrieve_criteria(goal, decision="HITL")
    if not hitl_rule:
        return {
            "approvalRequired": False,
            "reason": "No human approval scenario matched.",
            "requirements": [],
        }

    return {
        "approvalRequired": True,
        "reviewer": "Teacher or administrator",
        "reason": hitl_rule.reason,
        "requirements": [hitl_rule.requirement],
        "proposalObjective": proposal["objective"],
    }


# ============================================================
# Scientist Agent
# ============================================================
# 1. The Scientist Agent creates the proposal.
# 2. It does not approve experiments.
# 3. It withholds procedural detail when the safety profile is hazardous.

def infer_study_type(goal: str) -> dict[str, Any]:
    """Infer a classroom-scale study shape from the entered goal."""
    lower = goal.lower()

    if re.search(r"plant|seed|soil|water quality|germination|growth", lower):
        return {
            "variable": "environmental condition",
            "measurement": "growth, visible change, or count data",
            "materials": [
                "household containers",
                "labels",
                "measuring tool",
                "observation sheet",
                "teacher-approved samples",
            ],
        }

    if re.search(r"temperature|insulat|heat loss|warm|cool", lower):
        return {
            "variable": "material or temperature condition",
            "measurement": "temperature readings over time",
            "materials": [
                "cups",
                "thermometer",
                "timer",
                "household insulating materials",
                "data table",
            ],
        }

    if re.search(r"light|color|sound|motion|force|friction|magnet", lower):
        return {
            "variable": "physical condition",
            "measurement": "repeatable observations or simple measurements",
            "materials": [
                "classroom-safe test objects",
                "ruler or timer",
                "labels",
                "data table",
            ],
        }

    return {
        "variable": "one controlled variable",
        "measurement": "repeatable observations and simple measurements",
        "materials": [
            "household or classroom-safe materials",
            "labels",
            "measuring tool",
            "observation sheet",
        ],
    }


def scientist_agent(goal: str, cost: int) -> dict[str, Any]:
    """Create an experiment proposal from the research goal."""
    reject_rule = retrieve_criteria(goal, decision="REJECT")
    study_type = infer_study_type(goal)
    objective_goal = sentence_case(re.sub(r"[.?!]+$", "", goal))
    hazardous = reject_rule is not None

    return {
        "objective": objective_goal,
        "hypothesis": f"If students vary {study_type['variable']}, then {study_type['measurement']} will show whether the goal is supported by evidence.",
        "materials": (
            [
                "Materials withheld pending safety review",
                "non-hazardous simulation or teacher-approved substitute",
                "observation sheet",
            ]
            if hazardous
            else study_type["materials"]
        ),
        "methodology": (
            "Do not run the proposed activity as written. Convert the goal into a non-hazardous simulation, demonstration video analysis, or teacher-approved substitute before any classroom use."
            if hazardous
            else "Set up a small controlled comparison, change one variable at a time, collect repeated observations, and summarize results in a table or chart."
        ),
        "outcomes": "Students practice hypothesis formation, controls, measurement, evidence-based explanation, and responsible review of safety and resource constraints.",
        "cost": cost,
    }


# ============================================================
# LLM safety sanity check
# ============================================================
# 1. RAG criteria still handles explicit reject, modify, and HITL cases first.
# 2. When RAG finds no problem, the LLM does a second-pass reasonableness check.
# 3. Missing or failed LLM review cannot be treated as approval.

def llm_safety_sanity_check(goal: str, proposal: dict[str, Any]) -> dict[str, Any]:
    """Ask an LLM whether a RAG-cleared proposal is reasonably classroom-safe."""
    api_key, api_key_source = get_openai_api_key()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    student_controls_present = student_measurement_controls_present(goal, proposal)

    if not api_key or api_key.startswith("replace-with"):
        return {
            "decision": "MODIFY",
            "reason": "RAG criteria found no explicit hazard, but the OpenAI safety sanity check is not configured.",
            "requirements": ["Add OPENAI_API_KEY to .env locally or to Vercel Production environment variables before allowing automatic safety approval."],
            "matchedCriteria": "llm safety check unavailable",
        }

    prompt = {
        "research_goal": goal,
        "proposal": proposal,
        "local_student_measurement_detector": {
            "basic_safeguards_appear_present": student_controls_present,
            "instruction": (
                "If true, approve the physical-safety review unless a hard unsafe condition is present. "
                "Administrative consent/privacy concerns are handled by the separate HUMAN REVIEW step."
            ),
        },
        "review_task": (
            "Decide whether this is a reasonable supervised classroom experiment for K-12 or introductory students. "
            "Do not provide dangerous procedural instructions. Prefer MODIFY when controls are needed. "
            "Do not turn consent, privacy, or school-policy concerns into a safety MODIFY when the activity already includes consent, anonymous data, teacher supervision, and light exercise; those concerns are escalated separately through HUMAN REVIEW. "
            "Reject if it involves hazardous chemicals, unknown hazardous materials, biological agents, explosives, high voltage, high heat, illegal activity, or unsafe human-subject activity."
        ),
        "allowed_decisions": ["APPROVE", "MODIFY", "REJECT"],
        "required_json_shape": {
            "decision": "APPROVE | MODIFY | REJECT",
            "reason": "one sentence",
            "requirements": ["short required action"],
        },
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a cautious classroom lab safety reviewer. "
                    "Return only valid JSON. Never approve if safety is ambiguous."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt),
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    request = Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, IncompleteRead, RemoteDisconnected, json.JSONDecodeError) as exc:
        return {
            "decision": "MODIFY",
            "reason": f"RAG criteria found no explicit hazard, but the OpenAI safety sanity check could not complete: {type(exc).__name__}.",
            "requirements": ["Have the teacher review the activity or retry after the LLM safety check is available."],
            "matchedCriteria": "llm safety check failed",
        }

    content = (
        raw_response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "{}")
    )

    try:
        llm_review = json.loads(content)
    except json.JSONDecodeError:
        return {
            "decision": "MODIFY",
            "reason": "RAG criteria found no explicit hazard, but the LLM safety response was not valid JSON.",
            "requirements": ["Have the teacher review the activity before classroom use."],
            "matchedCriteria": "llm safety check invalid response",
        }

    decision = str(llm_review.get("decision", "")).upper()
    if decision not in {"APPROVE", "MODIFY", "REJECT"}:
        decision = "MODIFY"
    if decision == "REJECT":
        decision = "MODIFY"

    requirements = llm_review.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        requirements = ["Keep quantities small, use teacher-approved materials, and supervise measurements."]

    if student_controls_present and decision != "REJECT":
        return {
            "decision": "APPROVE",
            "reason": "Basic student-measurement safeguards are already included, and the LLM safety check did not identify a hard rejection.",
            "requirements": ["Continue using consent, anonymous recording, teacher supervision, and light activity limits."],
            "matchedCriteria": "RAG clear + LLM safety sanity check",
            "llmReason": str(llm_review.get("reason") or ""),
            "llmKeySource": api_key_source,
        }

    return {
        "decision": decision,
        "reason": str(llm_review.get("reason") or "LLM safety sanity check completed."),
        "requirements": [str(item) for item in requirements],
        "matchedCriteria": "RAG clear + LLM safety sanity check",
        "llmKeySource": api_key_source,
    }


def llm_modify_mitigation_check(
    goal: str,
    proposal: dict[str, Any],
    modify_rule: CriteriaRule,
) -> dict[str, Any]:
    """Ask an LLM whether a RAG MODIFY requirement is already addressed."""
    api_key, api_key_source = get_openai_api_key()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    controls_present = mitigation_controls_present(goal, proposal, modify_rule)

    if not api_key:
        return {
            "decision": "MODIFY",
            "reason": f"{modify_rule.reason} The LLM mitigation check is not configured.",
            "requirements": [modify_rule.requirement],
            "matchedCriteria": modify_rule.label,
        }

    prompt = {
        "research_goal": goal,
        "proposal": proposal,
        "rag_modify_match": {
            "label": modify_rule.label,
            "reason": modify_rule.reason,
            "required_action": modify_rule.requirement,
        },
        "local_mitigation_detector": {
            "required_controls_appear_present": controls_present,
            "instruction": "Use this as supporting evidence, but still reject if a hard unsafe condition is present.",
        },
        "review_task": (
            "RAG found a MODIFY-level classroom safety concern. Determine whether the user's goal or the generated proposal "
            "already includes the required action or equivalent controls. Approve only if the controls are clearly present. "
            "For this demo, treat explicit commitments such as teacher supervision, small quantities, clear labels, cleanup, "
            "safe handling, sealed containers, gloves, or allergy checks as sufficient when they match the RAG required action. "
            "Do not require a detailed standard operating procedure. Keep MODIFY only if a required control category is missing "
            "or vague. Reject only if the proposal contains a hard unsafe condition."
        ),
        "allowed_decisions": ["APPROVE", "MODIFY", "REJECT"],
        "required_json_shape": {
            "decision": "APPROVE | MODIFY | REJECT",
            "reason": "one sentence",
            "requirements": ["short required action"],
        },
    }

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a cautious classroom lab safety reviewer. "
                    "Return only valid JSON. Do not add procedural detail for dangerous experiments."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt),
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    request = Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, IncompleteRead, RemoteDisconnected, json.JSONDecodeError) as exc:
        return {
            "decision": "MODIFY",
            "reason": f"{modify_rule.reason} The LLM mitigation check could not complete: {type(exc).__name__}.",
            "requirements": [modify_rule.requirement],
            "matchedCriteria": modify_rule.label,
        }

    content = (
        raw_response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "{}")
    )

    try:
        llm_review = json.loads(content)
    except json.JSONDecodeError:
        return {
            "decision": "MODIFY",
            "reason": f"{modify_rule.reason} The LLM mitigation response was not valid JSON.",
            "requirements": [modify_rule.requirement],
            "matchedCriteria": modify_rule.label,
        }

    decision = str(llm_review.get("decision", "")).upper()
    if decision not in {"APPROVE", "MODIFY", "REJECT"}:
        decision = "MODIFY"

    requirements = llm_review.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        requirements = (
            ["No further safety changes required."]
            if decision == "APPROVE"
            else [modify_rule.requirement]
        )

    if controls_present and decision != "REJECT":
        return {
            "decision": "APPROVE",
            "reason": "The RAG-required safety controls are already included, and the LLM mitigation check did not identify a hard rejection.",
            "requirements": ["Continue using the stated controls during the classroom activity."],
            "matchedCriteria": f"{modify_rule.label} + LLM mitigation check",
            "ragRequirement": modify_rule.requirement,
            "llmReason": str(llm_review.get("reason") or ""),
            "llmKeySource": api_key_source,
        }

    return {
        "decision": decision,
        "reason": str(llm_review.get("reason") or modify_rule.reason),
        "requirements": [str(item) for item in requirements],
        "matchedCriteria": f"{modify_rule.label} + LLM mitigation check",
        "ragRequirement": modify_rule.requirement,
        "llmKeySource": api_key_source,
    }


def openai_runtime_status() -> dict[str, Any]:
    """Return non-secret OpenAI runtime configuration status."""
    api_key, api_key_source = get_openai_api_key()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    configured = bool(api_key)
    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8] if configured else None
    checked_names = {
        name: bool(os.environ.get(name, "").strip())
        for name in OPENAI_API_KEY_ENV_NAMES
    }

    return {
        "openaiConfigured": configured,
        "model": model,
        "keySource": api_key_source,
        "checkedKeyNames": checked_names,
        "keyFingerprint": fingerprint,
        "keyLength": len(api_key) if configured else 0,
    }


# ============================================================
# Safety Officer Agent
# ============================================================
# 1. The Safety Officer retrieves criteria from the local RAG file.
# 2. Rejection rules outrank modification rules.
# 3. MODIFY rules get an LLM mitigation check before remaining MODIFY.
# 4. If RAG finds no issue, an LLM performs a second-pass safety sanity check.

def safety_officer_agent(goal: str, proposal: dict[str, Any]) -> dict[str, Any]:
    """Review safety using RAG-backed criteria plus an LLM sanity check."""
    reject_rule = retrieve_criteria(goal, decision="REJECT")
    if reject_rule:
        return {
            "decision": "REJECT",
            "reason": reject_rule.reason,
            "requirements": [reject_rule.requirement],
            "matchedCriteria": reject_rule.label,
        }

    modify_rule = retrieve_criteria(goal, decision="MODIFY")
    if modify_rule:
        return llm_modify_mitigation_check(goal, proposal, modify_rule)

    return llm_safety_sanity_check(goal, proposal)


# ============================================================
# Budget Analyst Agent
# ============================================================
# 1. The Budget Analyst uses the guarded budget review tool.
# 2. The agent returns approve, modify, or reject.
# 3. It cannot override the Safety Officer.

def budget_analyst_agent(proposal: dict[str, Any], policy: dict[str, int]) -> dict[str, Any]:
    """Review cost and resource requirements."""
    return budget_review_tool(proposal["cost"], policy)


# ============================================================
# Handoff triage agent
# ============================================================
# 1. The orchestrator hands work to each specialist in sequence.
# 2. This mirrors the handoff example without requiring a network model call.
# 3. Each specialist owns one decision surface.

def handoff_to_scientist(goal: str, cost: int) -> dict[str, Any]:
    """Handoff to the Scientist Agent."""
    return scientist_agent(goal, cost)


def handoff_to_safety(goal: str, proposal: dict[str, Any]) -> dict[str, Any]:
    """Handoff to the Lab Safety Officer Agent."""
    return safety_officer_agent(goal, proposal)


def handoff_to_budget(proposal: dict[str, Any], policy: dict[str, int]) -> dict[str, Any]:
    """Handoff to the Budget Analyst Agent."""
    return budget_analyst_agent(proposal, policy)


# ============================================================
# Final decision logic
# ============================================================
# 1. Safety and budget rejection blocks approval.
# 2. HITL approval escalates when no hard rejection happened.
# 3. Modification requests require proposal changes before approval.

def evaluate_reviews(
    safety: dict[str, Any],
    budget: dict[str, Any],
    hitl: dict[str, Any],
) -> dict[str, str]:
    """Combine reviewer decisions into one final orchestrator decision."""
    decisions = [safety["decision"], budget["decision"]]

    if "REJECT" in decisions:
        return {
            "decision": "REJECTED",
            "explanation": "At least one required reviewer rejected the proposal, so the orchestrator cannot approve or modify it.",
        }

    if hitl["approvalRequired"]:
        return {
            "decision": "HUMAN REVIEW",
            "explanation": f"Human approval is required. {hitl['reason']}",
        }

    if "MODIFY" in decisions:
        return {
            "decision": "MODIFY",
            "explanation": "At least one required reviewer requested changes. Required changes must be addressed before approval.",
        }

    if len(set(decisions)) > 1:
        return {
            "decision": "HUMAN REVIEW",
            "explanation": "Reviewer decisions conflict in a way the policy cannot safely resolve automatically.",
        }

    return {
        "decision": "APPROVED",
        "explanation": "Both required reviewers approved the proposal.",
    }


# ============================================================
# Run the orchestrator
# ============================================================
# 1. The browser sends JSON to api/orchestrate.py.
# 2. The API calls orchestrate().
# 3. The returned JSON drives the UI and audit trail.

def orchestrate(payload: dict[str, Any]) -> dict[str, Any]:
    """Coordinate input guardrails, handoffs, tool guardrails, HITL, and final decision."""
    goal = normalize_goal(payload.get("goal"))
    cost = normalize_cost(payload.get("cost"))
    policy = normalize_budget_policy(payload.get("budgetPolicy"))
    required_fields = required_fields_guardrail(goal, cost, policy)

    if not required_fields["valid"]:
        raise ValueError(required_fields["reason"])

    audit = [f"Research goal received: {goal}"]
    logic_check = experiment_logic_guardrail(goal)

    if not logic_check["valid"]:
        audit.append(f"Input guardrail blocked the request. {logic_check['reason']}")
        return {
            "status": "invalid",
            "goal": goal,
            "logicCheck": logic_check,
            "finalDecision": "INVALID GOAL",
            "explanation": logic_check["reason"],
            "audit": audit,
        }

    audit.append("Input guardrail passed. The goal is valid for this classroom workflow.")
    proposal = handoff_to_scientist(goal, cost)
    audit.append(
        f"Handoff to Scientist Agent complete. Proposal cost: ${proposal['cost']:,}."
    )

    safety = handoff_to_safety(goal, proposal)
    audit.append(
        f"Handoff to Lab Safety Officer complete. Decision: {safety['decision']}. {safety['reason']}"
    )

    budget = handoff_to_budget(proposal, policy)
    audit.append(
        f"Handoff to Budget Analyst complete. Decision: {budget['decision']}. {budget['reason']}"
    )

    hitl = human_approval_check(goal, proposal)
    if hitl["approvalRequired"]:
        audit.append(
            f"HITL approval required from {hitl['reviewer']}. {hitl['reason']}"
        )

    final = evaluate_reviews(safety, budget, hitl)
    audit.append(f"Orchestrator final decision: {final['decision']}. {final['explanation']}")

    return {
        "status": "ok",
        "goal": goal,
        "logicCheck": logic_check,
        "proposal": proposal,
        "safetyReview": safety,
        "budgetReview": budget,
        "humanApproval": hitl,
        "finalDecision": final["decision"],
        "explanation": final["explanation"],
        "audit": audit,
    }
