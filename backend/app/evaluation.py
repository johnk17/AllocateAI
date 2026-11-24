"""Authorized, de-identified extraction evaluation; raw inputs are never returned."""

from types import SimpleNamespace
from .skills import match_skills, exact_skill, claim_supported


def extraction_evaluation(records, skills, provider):
    totals = {
        m: {"tp": 0, "fp": 0, "fn": 0, "qual_correct": 0, "unsupported": 0}
        for m in ("keyword", "alias", "llm")
    }
    live_error = None

    def accumulate(mode, predicted, gold, qual_correct, unsupported=0):
        t = totals[mode]
        t["tp"] += len(predicted & gold)
        t["fp"] += len(predicted - gold)
        t["fn"] += len(gold - predicted)
        t["qual_correct"] += qual_correct
        t["unsupported"] += unsupported

    for record in records:
        text = record["text"]
        gold = set(record["gold_skill_ids"])
        qualifications = set(record.get("gold_qualifications", []))
        for mode in ("keyword", "alias"):
            catalog = [
                SimpleNamespace(
                    id=s.id, name=s.name, aliases=[] if mode == "keyword" else s.aliases
                )
                for s in skills
            ]
            hits = match_skills(text, catalog)
            supported = [
                h
                for h in hits
                if claim_supported(
                    "skill",
                    h["value"],
                    h["excerpt"],
                    next(s for s in skills if s.id == h["skill_id"]),
                )
            ]
            accumulate(
                mode,
                {h["skill_id"] for h in supported},
                gold,
                not qualifications,
                len(hits) - len(supported),
            )
        if provider.mode == "live":
            try:
                extracted = provider.extract([{"page": 1, "text": text}], "")
                predicted = set()
                predicted_q = set()
                unsupported = 0
                for c in extracted.claims:
                    skill = exact_skill(c.value, skills) if c.kind == "skill" else None
                    valid = c.excerpt in text and claim_supported(
                        c.kind, c.value, c.excerpt, skill
                    )
                    if not valid:
                        unsupported += 1
                        continue
                    if c.kind == "skill":
                        predicted.add(skill.id)
                    if c.kind == "qualification":
                        predicted_q.add(c.value)
                accumulate(
                    "llm", predicted, gold, predicted_q == qualifications, unsupported
                )
            except Exception as exc:
                live_error = type(exc).__name__
    results = {}
    for mode, t in totals.items():
        ran = mode != "llm" or (provider.mode == "live" and not live_error)
        results[mode] = {
            "status": "completed"
            if ran
            else "not_run_no_live_model"
            if provider.mode != "live"
            else "failed_provider_" + str(live_error),
            "skill_precision": t["tp"] / (t["tp"] + t["fp"])
            if ran and t["tp"] + t["fp"]
            else None,
            "skill_recall": t["tp"] / (t["tp"] + t["fn"])
            if ran and t["tp"] + t["fn"]
            else None,
            "qualification_exact_set_accuracy": t["qual_correct"] / len(records)
            if ran and records
            else None,
            "unsupported_claims_detected": t["unsupported"] if ran else None,
        }
    return {
        "record_count": len(records),
        "results": results,
        "privacy": "Raw text, identifiers and excerpts are not returned or persisted. Keyword/alias baselines do not infer qualifications; manual review is required.",
    }
