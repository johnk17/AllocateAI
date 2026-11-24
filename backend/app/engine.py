"""Deterministic matching, CP-SAT, and an independent publication verifier."""

import hashlib
import json
from collections import Counter
from datetime import date
import re
from ortools.sat.python import cp_model
from .internship_matching import academic_fields, is_managed, profile_academics, source_open


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def listing_status(details):
    if is_managed(details):
        status = details.get("status", "unverified")
        return "unverified" if status == "open" and not source_open(details) else status
    if details.get("deadline") and details["deadline"] < date.today().isoformat():
        return "expired"
    if details.get("status") == "open":
        try:
            days = (
                date.today() - date.fromisoformat(details.get("last_verified") or "")
            ).days
        except (TypeError, ValueError):
            return "unverified"
        if not 0 <= days <= 30 or details.get("source_approved") is not True:
            return "unverified"
        if not details.get("deadline") and not details.get("rolling"):
            return "unverified"
    return details.get("status", "unverified")


def city(value):
    name = (value or "").split(",", 1)[0].strip().casefold()
    return {"bangalore": "bengaluru", "bombay": "mumbai", "gurgaon": "gurugram"}.get(name, name)


def source_locations(i):
    return [loc for loc in i.get("source_locations", [i.get("location")]) if loc]


def role_terms(value):
    value = re.sub(r"\bsde\b", "software engineer", value.casefold())
    value = re.sub(r"\b(?:engineer(?:ing)?|developer|development)\b", "engineering", value)
    return set(re.findall(r"[a-z0-9]+", value)) - {"intern", "internship", "associate", "the", "and", "of"}


def eligible(a, i, rules):
    failed = []
    unresolved = []
    if listing_status(i) != "open":
        failed.append("Listing is expired or unverified")
    qualifications = set(a.get("qualifications", []))
    for q in i.get("mandatory_qualifications", []):
        if q not in qualifications:
            if q in a.get("rejected_qualifications", []):
                failed.append(f"Mandatory qualification not held: {q}")
            else:
                unresolved.append(f"Unverified mandatory qualification: {q}")
    required = {
        r["skill_id"]
        for r in i.get("requirements", [])
        if r["classification"] == "required"
    }
    for skill in sorted(required - set(a.get("reviewed_skills", []))):
        unresolved.append(f"Required skill claim {skill} needs review")
    if rules.get("exclude_prior_participants"):
        if a.get("prior_participation_confirmed") is None:
            unresolved.append("Prior participation has not been confirmed")
        elif a["prior_participation_confirmed"]:
            failed.append("Prior participation excluded by approved configuration")
    if not a.get("willing_to_relocate", True):
        if i.get("work_mode") == "remote":
            pass
        elif not a.get("home_location") or not i.get("location"):
            unresolved.append("Location is unknown for checking relocation restriction")
        elif (
            i.get("work_mode") != "remote"
            and (city(a["home_location"]) not in {city(loc) for loc in source_locations(i)} if is_managed(i)
                 else i["location"].casefold() != a["home_location"].casefold())
        ):
            failed.append("Explicit relocation restriction")
    if not rules.get("coverage_confirmed"):
        unresolved.append("Approved applicable rule coverage is unconfirmed")
    if rules.get("require_noc") and not a.get("noc_confirmed"):
        unresolved.append(
            "The applicable rule requires reviewer-confirmed NOC evidence"
        )
    return {
        "decision": "FAIL" if failed else "REVIEW" if unresolved else "PASS",
        "policy_version": rules.get("policy_version"),
        "reason_codes": (["contradicted"] if failed else ["needs_evidence"] if unresolved else ["checks_passed"]),
        "scheme": rules.get("scheme"),
        "effective_date": rules.get("effective_date"),
        "status": "ineligible"
        if failed
        else "needs_review"
        if unresolved
        else "eligible",
        "reasons": failed or unresolved,
    }


FIT_WEIGHTS = {"technical": 50, "location": 20, "work_mode": 15, "sector_role": 15}
MIN_EVIDENCE_COVERAGE = 0.5
MAX_CHOICES = 5


def score(a, i, rules):
    employer_feed = is_managed(i)
    weights = dict(FIT_WEIGHTS)
    weights_by_skill = {}
    for req in i.get("requirements", []):
        weight = {"required": 2, "preferred": 1}.get(req["classification"])
        if employer_feed and req["classification"] == "mentioned":
            weight = 1
        if weight:
            sid = req["skill_id"]
            weights_by_skill[sid] = max(weight, weights_by_skill.get(sid, 0))
    target = set(weights_by_skill)
    accepted = set(a.get("skills", []))
    matched = target & accepted
    if employer_feed:
        accepted_names = set(a.get("accepted_skill_names", []))
        matched |= {sid for sid in target
                    if i.get("source_skill_names", {}).get(str(sid), "").casefold() in accepted_names}
    gaps = target - matched
    unresolved = i.get("unresolved_requirements") or (
        [i["requirements_text"]] if not target and i.get("requirements_text") else []
    )

    def fit(value, preferred):
        if not value or not preferred:
            return None
        return float(value.casefold() in {entry.casefold() for entry in preferred})

    components = {
        "technical": sum(weights_by_skill[k] for k in matched)
        / sum(weights_by_skill.values())
        if target
        else None,
        "location": fit(i.get("location"), a.get("preferred_locations")),
        "work_mode": fit(i.get("work_mode"), a.get("preferred_work_modes")),
        "sector_role": fit(i.get("sector"), a.get("preferred_sectors")),
    }
    if employer_feed:
        if i.get("location") and a.get("preferred_locations"):
            published_locations = {city(loc) for loc in source_locations(i)}
            components["location"] = float(bool(published_locations & {city(loc) for loc in a["preferred_locations"]}))
        desired = role_terms(a.get("preferred_role") or "")
        if desired - {"engineering"}:
            desired.discard("engineering")
        title = role_terms(i.get("title") or "")
        if desired and title:
            components["role"] = len(desired & title) / len(desired)
            weights["role"] = 25
        student_fields, degrees = profile_academics(a)
        posted_fields = set(i.get("academic_fields") or academic_fields(i.get("title") or ""))
        posted_degrees = set(i.get("source_education", [])) - {"computer science"}
        entered_degrees = degrees - {"computer science"}
        if student_fields and posted_fields:
            components["education"] = float(bool(student_fields & posted_fields))
            weights["education"] = 20
        if entered_degrees and posted_degrees:
            components["degree"] = float(bool(entered_degrees & posted_degrees))
            weights["degree"] = 10
        sector_fields = set().union(*(academic_fields(value) for value in a.get("preferred_sectors", [])))
        if sector_fields and posted_fields:
            components["sector_role"] = float(bool(sector_fields & posted_fields))
    denominator = sum(weights[k] for k, v in components.items() if v is not None)
    coverage = denominator / sum(weights.values())
    contributions = {
        k: round(v * weights[k] / denominator * 100, 4) if v is not None else None
        for k, v in components.items()
    }
    fit_score = (
        round(sum(v for v in contributions.values() if v is not None), 4)
        if denominator
        else None
    )
    return {
        "score": fit_score,
        "merit_score": fit_score,
        "components": components,
        "contributions": contributions,
        "active_weight_total": denominator,
        "evidence_coverage": coverage,
        "coverage_threshold_met": coverage >= MIN_EVIDENCE_COVERAGE,
        "skill_coverage": components["technical"],
        "skill_coverage_status": "unknown"
        if not target
        else "partial"
        if unresolved
        else "known",
        "unresolved_requirements": unresolved,
        "matched_skills": sorted(matched),
        **({"matched_skill_names": [i["source_skill_names"][str(sid)] for sid in sorted(matched)
                                    if str(sid) in i.get("source_skill_names", {})]} if employer_feed else {}),
        "missing_skills": sorted(gaps),
        "related_unverified": sorted(set(a.get("related_skills", [])) & gaps),
        "note": "Fit uses only known components. Listings below 50% evidence coverage appear after scored listings with sufficient evidence.",
    }


def pairs_for(applicants, listings, rules, ranked=True):
    pairs = []
    excluded = []
    for a in applicants:
        choices = a.get("rankings", []) if ranked else [i["id"] for i in listings]
        for rank, listing_id in enumerate(choices, 1):
            i = next((i for i in listings if i["id"] == listing_id), None)
            if not i:
                excluded.append(
                    {
                        "applicant_id": a["id"],
                        "listing_id": listing_id,
                        "status": "unavailable",
                        "reasons": ["Listing missing"],
                    }
                )
                continue
            check = eligible(a, i, rules)
            if ranked and not i.get("capacity"):
                check = {
                    "status": "recommendation_only",
                    "reasons": ["No positive confirmed seat count for this round"],
                }
            if check["status"] != "eligible":
                excluded.append(
                    {"applicant_id": a["id"], "listing_id": listing_id, **check}
                )
                continue
            pairs.append(
                {
                    "applicant_id": a["id"],
                    "listing_id": listing_id,
                    "rank": rank if ranked else None,
                    **(
                        {"utility": MAX_CHOICES + 1 - rank}
                        if ranked
                        else score(a, i, rules)
                    ),
                }
            )
    return pairs, excluded


def violations(placements, applicants, listings, rules, pairs):
    errors = []
    applicant_ids = {a["id"] for a in applicants}
    by_id = {i["id"]: i for i in listings}
    eligible_pairs = {(p["applicant_id"], p["listing_id"]): p for p in pairs}
    seen = Counter(p["applicant_id"] for p in placements)
    for aid, count in seen.items():
        if aid not in applicant_ids or count > 1:
            errors.append(f"Invalid or duplicate applicant {aid}")
    for p in placements:
        if (p["applicant_id"], p["listing_id"]) not in eligible_pairs:
            errors.append("Assignment not in eligible ranked pairs")
        else:
            match = eligible_pairs[(p["applicant_id"], p["listing_id"])]
            if p.get("rank") != match["rank"] or p.get("utility") != match.get(
                "utility"
            ):
                errors.append("Rank or rank utility does not match frozen choices")
    for lid, count in Counter(p["listing_id"] for p in placements).items():
        i = by_id.get(lid)
        if not i or i.get("capacity") is None or count > i["capacity"]:
            errors.append(
                f"Unconfirmed capacity or capacity exceeded for listing {lid}"
            )
    people = {a["id"]: a for a in applicants}
    groups = Counter(
        g
        for p in placements
        for g in people.get(p["applicant_id"], {}).get("groups", [])
    )
    for group, n in rules.get("minimum_placements", {}).items():
        if groups[group] < n:
            errors.append(f"{group}: minimum {n}, achieved {groups[group]}")
    return errors


def metrics(placements, applicants, listings, errors):
    n = len(placements)
    total = sum(i.get("capacity") or 0 for i in listings)
    by_id = {a["id"]: a for a in applicants}
    return {
        "placed": n,
        "seats": total,
        "fill_rate": round(n / total * 100, 2) if total else None,
        "first_choice_rate": round(sum(p["rank"] == 1 for p in placements) / n * 100, 2)
        if n
        else None,
        "preference_utility": sum(p["utility"] for p in placements),
        "district_coverage": len(
            {
                by_id[p["applicant_id"]]["district"]
                for p in placements
                if by_id[p["applicant_id"]].get("district")
            }
        ),
        "representation": dict(
            Counter(
                g
                for p in placements
                for g in by_id[p["applicant_id"]].get("groups", [])
            )
        ),
        "violations": errors,
    }


def optimize(applicants, listings, rules):
    pairs, excluded = pairs_for(applicants, listings, rules)
    model = cp_model.CpModel()
    # Stable per-round ordering based on a committed random seed and opaque participant IDs.
    salt = rules.get("tie_seed", "allocateai-isolated-fixture-v1")
    by_tie = lambda p: fingerprint([salt, p["applicant_id"], p["listing_id"]])
    pairs.sort(key=by_tie)
    variables = [model.new_bool_var(f"p{n}") for n in range(len(pairs))]
    for a in applicants:
        model.add(
            sum(v for v, p in zip(variables, pairs) if p["applicant_id"] == a["id"])
            <= 1
        )
    for i in listings:
        model.add(
            sum(v for v, p in zip(variables, pairs) if p["listing_id"] == i["id"])
            <= (i.get("capacity") or 0)
        )
    people = {a["id"]: a for a in applicants}
    assumptions = {}
    for group, n in rules.get("minimum_placements", {}).items():
        if not n:
            continue
        lit = model.new_bool_var("minimum_" + group)
        model.add(
            sum(
                v
                for v, p in zip(variables, pairs)
                if group in people[p["applicant_id"]].get("groups", [])
            )
            >= n
        ).only_enforce_if(lit)
        model.add_assumption(lit)
        assumptions[lit.index] = f"{group}: minimum {n}"
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 33
    count_objective = sum(variables)
    utility_objective = sum(v * p["utility"] for v, p in zip(variables, pairs))
    model.maximize(count_objective)
    first = solver.solve(model)
    first_name = solver.status_name(first)
    stage_1 = {
        "status": first_name,
        "value": int(solver.objective_value)
        if first in (cp_model.FEASIBLE, cp_model.OPTIMAL)
        else None,
        "bound": solver.best_objective_bound,
    }
    stage_2 = None
    tie_status = None
    placements, conflicts = [], []
    final = first
    if first == cp_model.OPTIMAL:
        model.add(count_objective == stage_1["value"])
        model.maximize(utility_objective)
        final = solver.solve(model)
        stage_2 = {
            "status": solver.status_name(final),
            "value": int(solver.objective_value)
            if final in (cp_model.FEASIBLE, cp_model.OPTIMAL)
            else None,
            "bound": solver.best_objective_bound,
        }
        if final in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            placements = [p for v, p in zip(variables, pairs) if solver.value(v)]
        if final == cp_model.OPTIMAL:
            # First solution in the seeded edge order, with both certified objectives fixed.
            model.add(utility_objective == stage_2["value"])
            model.clear_objective()
            model.add_decision_strategy(
                variables, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE
            )
            solver.parameters.search_branching = cp_model.FIXED_SEARCH
            solver.parameters.cp_model_presolve = False
            tie = solver.solve(model)
            tie_status = solver.status_name(tie)
            if tie == cp_model.OPTIMAL:
                placements = [p for v, p in zip(variables, pairs) if solver.value(v)]
    if first == cp_model.INFEASIBLE:
        conflicts = [
            assumptions.get(int(x), str(x))
            for x in solver.sufficient_assumptions_for_infeasibility()
        ]
    errors = violations(placements, applicants, listings, rules, pairs)
    # Same eligible pairs/capacities; group-minimum differences are disclosed and measured.
    greedy = []
    used = set()
    filled = Counter()
    capacities = {i["id"]: i.get("capacity") or 0 for i in listings}
    for p in sorted(
        pairs, key=lambda p: (fingerprint([salt, p["applicant_id"]]), p["rank"])
    ):
        if (
            p["applicant_id"] not in used
            and filled[p["listing_id"]] < capacities[p["listing_id"]]
        ):
            greedy.append(p)
            used.add(p["applicant_id"])
            filled[p["listing_id"]] += 1
    safe = (
        first == cp_model.OPTIMAL
        and final == cp_model.OPTIMAL
        and tie_status == "OPTIMAL"
        and not errors
    )
    selected = {p["applicant_id"] for p in placements}
    reasons = []
    for a in applicants:
        if a["id"] in selected:
            continue
        own = [e for e in excluded if e["applicant_id"] == a["id"]]
        reasons.append(
            {
                "applicant_id": a["id"],
                "reason": "No ranked choices"
                if not a.get("rankings")
                else "No eligible confirmed ranked pair"
                if not any(p["applicant_id"] == a["id"] for p in pairs)
                else "No seat under capacities, ranked choices and approved policy rules",
                "eligibility": own,
            }
        )
    return {
        "placements": placements,
        "unassigned": reasons,
        "pairs": pairs,
        "excluded": excluded,
        "solver_status": solver.status_name(final),
        "placement_status": first_name,
        "conflicts": conflicts,
        "objective_version": "lexicographic-rank-v1",
        "objectives": {"count": stage_1, "rank_utility": stage_2},
        "tie_status": tie_status,
        "deterministic_checks": errors,
        "publishable": safe,
        "metrics": metrics(placements, applicants, listings, errors),
        "baseline_metrics": metrics(
            greedy,
            applicants,
            listings,
            violations(greedy, applicants, listings, rules, pairs),
        ),
        "baseline_note": "Greedy uses identical eligible pairs and capacities, but does not enforce group minimums; violations are reported.",
        "input_snapshot": {
            "applicants": applicants,
            "listings": listings,
            "rules": rules,
        },
    }


def verify_draft(result):
    snapshot = result["input_snapshot"]
    pairs, excluded = pairs_for(
        snapshot["applicants"], snapshot["listings"], snapshot["rules"]
    )
    errors = violations(
        result["placements"],
        snapshot["applicants"],
        snapshot["listings"],
        snapshot["rules"],
        pairs,
    )
    objectives = result.get("objectives", {})
    expected = {
        "count": len(result["placements"]),
        "rank_utility": sum(p.get("utility", 0) for p in result["placements"]),
    }
    if (
        result.get("objective_version") != "lexicographic-rank-v1"
        or result.get("tie_status") != "OPTIMAL"
    ):
        errors.append("Unrecognized objective or uncertified tie resolution")
    for stage, value in expected.items():
        recorded = objectives.get(stage) or {}
        if (
            recorded.get("status") != "OPTIMAL"
            or recorded.get("value") != value
            or recorded.get("bound") != value
        ):
            errors.append(
                f"{stage} objective was not certified or does not match placements"
            )
    return errors
