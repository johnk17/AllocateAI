"""One graph with a preparation agent and a scoped policy evidence reviewer."""

from typing import TypedDict
from langgraph.runtime import Runtime
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from sqlalchemy import select
from .db import AgentCase, Evidence, Activity, Policy, Draft, Skill, revision
from .schemas import ToolCall
from .services import unresolved_case
from .retrieval import answer


class AgentState(TypedDict, total=False):
    case_id: str
    task: str
    draft_id: int
    question_available: bool
    policy_support: bool
    policy_retrieved: bool
    provider_error: bool
    selected: dict
    done: list[str]
    steps: int
    needs_review: bool
    ready: bool
    review_ack: bool


class RunContext(TypedDict, total=False):
    policy_question: str


def build_graph(Session, provider, embedder, checkpointer):
    def log(case_id, tool, outcome, next_action):
        with Session() as db:
            db.add(
                Activity(
                    case_id=case_id,
                    step="evidence_triage",
                    tool=tool,
                    outcome=outcome,
                    next_action=next_action,
                )
            )
            db.commit()

    def context(state):
        with Session() as db:
            case = db.get(AgentCase, state["case_id"])
            pending = unresolved_case(db, case)
            claims = list(
                db.scalars(
                    select(Evidence).where(Evidence.applicant_id == case.applicant_id)
                )
            )
            return {
                "done": state.get("done", []),
                "unresolved_required_count": len(pending),
                "claim_count": len(claims),
                "ambiguous_count": sum(
                    e.kind == "skill" and e.skill_id is None and e.status != "rejected"
                    for e in claims
                ),
                "has_policy_question": bool(state.get("question_available")),
                "policy_available": bool(case.policy_id),
            }

    def decide(state):
        c = context(state)
        done = state.get("done", [])
        if provider.mode == "fixture":
            if "inspect_resume_evidence" not in done:
                name = "inspect_resume_evidence"
            elif c["ambiguous_count"] and "resolve_skill_alias" not in done:
                name = "resolve_skill_alias"
            elif (
                c["has_policy_question"]
                and c["policy_available"]
                and "search_policy" not in done
            ):
                name = "search_policy"
            elif c["unresolved_required_count"]:
                name = "request_human_review"
            else:
                return {"ready": True}
            call = ToolCall(name=name)
        else:
            # Bounded loop. Regardless of model choice, the gate always checks evidence.
            if state.get("steps", 0) >= 6:
                return {"ready": True}
            try:
                if not provider.qualify():
                    raise ValueError("Configured provider did not pass a capability check")
                call = provider.choose(c)
                if call.arguments:
                    raise ValueError(
                        "Case-scoped tools do not accept user-selected arguments"
                    )
            except Exception:
                log(
                    state["case_id"],
                    "preparation",
                    {"provider_error": True},
                    "Use deterministic evidence validation",
                )
                return {"ready": True, "provider_error": True}
        return {
            "selected": call.model_dump(),
            "steps": state.get("steps", 0) + 1,
            "ready": False,
        }

    def tools(state, runtime: Runtime[RunContext]):
        call = ToolCall.model_validate(state["selected"])
        name = call.name
        if call.arguments:
            raise ValueError(
                "These case-scoped tools accept no model-selected identifiers or arguments"
            )
        policy_state = {}
        with Session() as db:
            case = db.get(AgentCase, state["case_id"])
            if name == "inspect_resume_evidence":
                pending = unresolved_case(db, case)
                outcome = {"unresolved_required_count": len(pending)}
            elif name == "resolve_skill_alias":
                ambiguous = list(
                    db.scalars(
                        select(Evidence).where(
                            Evidence.applicant_id == case.applicant_id,
                            Evidence.skill_id.is_(None),
                            Evidence.kind == "skill",
                            Evidence.status != "rejected",
                        )
                    )
                )
                catalog = list(
                    db.scalars(select(Skill).where(Skill.merged_into.is_(None)))
                )
                proposals = [
                    {
                        "evidence_id": e.id,
                        "canonical_skill_ids": [
                            s.id
                            for s in catalog
                            if e.value.casefold()
                            in [
                                s.name.casefold(),
                                *[alias.casefold() for alias in s.aliases],
                            ]
                        ],
                    }
                    for e in ambiguous
                ]
                outcome = {
                    "ambiguous_claim_count": len(ambiguous),
                    "alias_candidates": proposals,
                    "automatic_verification": False,
                }
            elif name == "search_policy":
                policy = db.get(Policy, case.policy_id) if case.policy_id else None
                query = (runtime.context or {}).get("policy_question")
                result = (
                    answer(db, query, policy, embedder)
                    if query and policy and policy.approved_by
                    else {"supported": False, "citations": []}
                )
                citations = result["citations"]
                valid = result["supported"] and bool(citations)
                ids = {c["passage_id"] for c in citations}
                if valid and provider.mode == "live" and not state.get("provider_error"):
                    try:
                        review = provider.review_policy(citations)
                        valid = (
                            review.verdict == "supported"
                            and set(review.passage_ids) == ids
                        )
                    except Exception:
                        valid = False
                policy_state = {"policy_retrieved": True, "policy_support": valid}
                log(
                    case.id,
                    "evidence_reviewer",
                    {
                        "supported": valid,
                        "mode": provider.mode,
                        "passage_ids": sorted(ids),
                    },
                    "Validate scoped evidence" if valid else "Review or abstain",
                )
                outcome = {
                    "supported": result["supported"],
                    "passage_ids": [c["passage_id"] for c in result["citations"]],
                    "retrieval_only": True,
                }
            else:
                outcome = {"review_requested": True}
        log(
            case.id,
            name,
            outcome,
            "Authorized evidence review"
            if name == "request_human_review"
            else "Continue triage",
        )
        return {
            "done": [*state.get("done", []), name],
            "needs_review": name == "request_human_review",
            **policy_state,
        }

    def gate(state):
        with Session() as db:
            case = db.get(AgentCase, state["case_id"])
            pending = unresolved_case(db, case)
            case.status = "needs_review" if pending else "ready"
            case.revision = revision(db)
            db.commit()
        if pending:
            log(
                case.id,
                "deterministic_gate",
                {"unresolved_required_count": len(pending)},
                "Pause for evidence review",
            )
        return {"needs_review": bool(pending), "ready": not pending}

    def review(state):
        # No side effects before interrupt: LangGraph replays this node on resume.
        response = interrupt(
            {
                "type": "evidence_review",
                "case_id": state["case_id"],
                "message": "An authorized admin must verify or reject required evidence before resuming.",
            }
        )
        if not response.get("authorized_review"):
            raise ValueError("Authorized review required")
        return {"done": [], "steps": 0}

    def draft_review(state):
        with Session() as db:
            draft = db.get(Draft, state["draft_id"])
            digest = draft.digest
        response = interrupt(
            {
                "type": "draft_approval",
                "draft_id": state["draft_id"],
                "digest": digest,
                "message": "Admin approval must match this exact draft and policy version.",
            }
        )
        if response.get("digest") != digest or not response.get("authorized_review"):
            raise ValueError("Draft approval mismatch")
        return {"review_ack": True}

    graph = StateGraph(AgentState, context_schema=RunContext)
    for name, fn in [
        ("decide", decide),
        ("tools", tools),
        ("gate", gate),
        ("review", review),
        ("draft_review", draft_review),
    ]:
        graph.add_node(name, fn)
    graph.add_conditional_edges(
        START, lambda s: "draft_review" if s.get("task") == "draft_review" else "decide"
    )
    graph.add_conditional_edges(
        "decide", lambda s: "gate" if s.get("ready") else "tools"
    )
    graph.add_conditional_edges(
        "tools",
        lambda s: (
            "gate" if s.get("needs_review") or s.get("steps", 0) >= 6 else "decide"
        ),
    )
    graph.add_conditional_edges(
        "gate", lambda s: "review" if s.get("needs_review") else END
    )
    graph.add_edge("review", "gate")
    graph.add_edge("draft_review", END)
    return graph.compile(checkpointer=checkpointer)


def graph_config(thread_id):
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 30}
