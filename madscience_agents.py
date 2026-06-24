import re


def normalize_goal(goal):
    return re.sub(r"\s+", " ", str(goal or "").strip())


def normalize_cost(cost):
    try:
        value = float(cost)
    except (TypeError, ValueError):
        return None
    return round(value) if value >= 0 else None


def normalize_budget_policy(policy):
    policy = policy or {}
    approve_max = normalize_cost(policy.get("approveMax"))
    reject_at = normalize_cost(policy.get("rejectAt"))

    if approve_max is None or reject_at is None or reject_at <= approve_max:
        return None

    return {"approveMax": approve_max, "rejectAt": reject_at}


def sentence_case(value):
    clean = str(value or "").strip()
    return clean[:1].upper() + clean[1:]


def check_experiment_logic(goal):
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


def identify_safety_profile(goal):
    lower = goal.lower()
    reject_rules = [
        (
            r"high[- ]?voltage|electrocution|mains electricity|tesla coil|visible arcs?|power supply",
            "high voltage",
        ),
        (
            r"explosive|explosion|detonation|gunpowder|firework|rocket fuel|propellant",
            "explosives or energetic materials",
        ),
        (
            r"hazardous (material|substance|chemical)|toxic material|toxic substance|strong acid|strong base|cyanide|mercury|chlorine gas|toxic gas|poison",
            "hazardous materials or chemicals",
        ),
        (
            r"pathogen|virus|bacteria|mold|blood|bodily fluid|biological agent|culture unknown microbes",
            "biological agents",
        ),
        (
            r"open flame|torch|combustion|burning|boiling oil|high heat|furnace",
            "high heat",
        ),
        (
            r"animal testing|human subject|medical treatment|drug|illegal",
            "regulated or illegal activity",
        ),
    ]
    modify_rules = [
        (
            r"warm water|hot water|heat|temperature|yeast|baker'?s yeast|vinegar|baking soda|salt|sugar|caffeine|magnet|sharp|scissors",
            "minor classroom hazard",
        ),
        (
            r"unknown water sample|outdoor sample|pond water|stream water|river water|lake water|soil sample|food handling|allergen|peanut|tree nut",
            "materials that need handling controls",
        ),
    ]

    for pattern, label in reject_rules:
        if re.search(pattern, lower):
            return {"risk": "hazardous", "trigger": label}

    for pattern, label in modify_rules:
        if re.search(pattern, lower):
            return {"risk": "minor", "trigger": label}

    return {"risk": "household", "trigger": "household materials only"}


def infer_study_type(goal):
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


def infer_proposal(goal, cost):
    safety_profile = identify_safety_profile(goal)
    study_type = infer_study_type(goal)
    objective_goal = sentence_case(re.sub(r"[.?!]+$", "", goal))
    hazardous = safety_profile["risk"] == "hazardous"

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
        "risk": safety_profile["risk"],
        "safetyTrigger": safety_profile["trigger"],
    }


def review_safety(proposal):
    if proposal["risk"] == "hazardous":
        return {
            "decision": "REJECT",
            "reason": f"The proposal appears to involve {proposal['safetyTrigger']}. Classroom instructions are not allowed for that risk category.",
            "requirements": [
                "Replace with a non-hazardous simulation, video analysis, or teacher-approved substitute."
            ],
        }

    if proposal["risk"] == "minor":
        return {
            "decision": "MODIFY",
            "reason": f"The proposal is mostly classroom-safe but includes {proposal['safetyTrigger']}, so it needs tighter controls.",
            "requirements": [
                "Add teacher supervision, small quantities, cleanup, labeling, and handwashing or handling procedures as appropriate."
            ],
        }

    return {
        "decision": "APPROVE",
        "reason": "Materials are household-level and the procedure avoids dangerous heat, voltage, chemicals, and biological agents.",
        "requirements": ["Keep quantities small and supervise measurements."],
    }


def review_budget(proposal, policy):
    cost = proposal["cost"]

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


def evaluate_reviews(safety, budget):
    decisions = [safety["decision"], budget["decision"]]

    if "REJECT" in decisions:
        return {
            "decision": "REJECTED",
            "explanation": "At least one required reviewer rejected the proposal, so the orchestrator cannot approve or modify it.",
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


def orchestrate(payload):
    goal = normalize_goal(payload.get("goal"))
    cost = normalize_cost(payload.get("cost"))
    policy = normalize_budget_policy(payload.get("budgetPolicy"))

    if not goal:
        raise ValueError("A research goal is required.")
    if cost is None:
        raise ValueError("A valid estimated cost is required.")
    if policy is None:
        raise ValueError("Budget thresholds are invalid. Reject-from must be greater than approve-up-to.")

    audit = [f"Research goal received: {goal}"]
    logic_check = check_experiment_logic(goal)

    if not logic_check["valid"]:
        audit.append(f"Experiment logic check failed. {logic_check['reason']}")
        return {
            "status": "invalid",
            "goal": goal,
            "logicCheck": logic_check,
            "finalDecision": "INVALID GOAL",
            "explanation": logic_check["reason"],
            "audit": audit,
        }

    audit.append("Experiment logic check passed. The goal is valid for this classroom workflow.")
    proposal = infer_proposal(goal, cost)
    audit.append(
        f"Scientist Agent produced proposal with estimated cost ${proposal['cost']:,} and risk category {proposal['risk']}."
    )

    safety = review_safety(proposal)
    audit.append(f"Lab Safety Officer decision: {safety['decision']}. {safety['reason']}")

    budget = review_budget(proposal, policy)
    audit.append(f"Budget Analyst decision: {budget['decision']}. {budget['reason']}")

    final = evaluate_reviews(safety, budget)
    audit.append(f"Orchestrator final decision: {final['decision']}. {final['explanation']}")

    return {
        "status": "ok",
        "goal": goal,
        "logicCheck": logic_check,
        "proposal": proposal,
        "safetyReview": safety,
        "budgetReview": budget,
        "finalDecision": final["decision"],
        "explanation": final["explanation"],
        "audit": audit,
    }
