import os
import re
from collections import defaultdict
from datetime import date
from sqlalchemy import select, func, text
from .db import Passage, PolicyDocument, Policy, PolicyProvenance

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    def __init__(self):
        self.model = None
        self.attempted = False
        self.detail = "Not loaded yet"

    def encode(self, texts):
        if not self.attempted:
            self.attempted = True
            try:
                if os.getenv("EMBEDDING_MODE", "sentence_transformers") == "keyword":
                    raise RuntimeError("keyword-only mode selected")
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(
                    MODEL,
                    local_files_only=os.getenv("ALLOW_MODEL_DOWNLOAD", "0") != "1",
                )
                self.detail = MODEL
            except Exception as exc:
                self.detail = (
                    f"Vector unavailable ({type(exc).__name__}); keyword-only retrieval"
                )
        return (
            self.model.encode(texts, normalize_embeddings=True).tolist()
            if self.model is not None
            else None
        )


def rrf(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] += 1 / (k + rank)
    return sorted(scores, key=lambda item: (-scores[item], item))


def retrieve(db, question, policy, embedder, mode="hybrid", limit=5):
    selected_date = policy.config.get("effective_date") or date.today().isoformat()
    scheme = policy.config.get("scheme")
    ids = []
    if policy.approved_by:
        for doc_id in policy.document_ids:
            doc = db.get(PolicyDocument, doc_id)
            meta = db.get(PolicyProvenance, doc_id)
            if (
                not doc
                or not meta
                or not meta.details.get("approved")
                or doc.effective_date > selected_date
            ):
                continue
            if scheme and meta.details.get("scheme") != scheme:
                continue
            if (
                meta.details.get("effective_until")
                and meta.details["effective_until"] < selected_date
            ):
                continue
            ids.append(doc_id)
    if not ids:
        return [], {
            "mode": "keyword",
            "vector_available": False,
            "reason": "No approved versioned documents in the effective scope",
        }
    base = select(Passage).where(Passage.document_id.in_(ids))
    if db.bind.dialect.name == "postgresql":
        query = func.websearch_to_tsquery("english", question)
        vector = func.to_tsvector("english", Passage.content)
        keyword = list(
            db.scalars(
                base.where(vector.op("@@")(query))
                .order_by(func.ts_rank_cd(vector, query).desc(), Passage.id)
                .limit(30)
            )
        )
    else:  # Test double only; real retrieval integration tests use PostgreSQL.
        terms = set(re.findall(r"\w+", question.lower()))
        all_rows = list(db.scalars(base))
        keyword = sorted(
            [p for p in all_rows if terms & set(re.findall(r"\w+", p.content.lower()))],
            key=lambda p: (
                -len(terms & set(re.findall(r"\w+", p.content.lower()))),
                p.id,
            ),
        )[:30]
    embedded = (
        embedder.encode([question])
        if mode != "keyword" and db.bind.dialect.name == "postgresql"
        else None
    )
    vector_rows = []
    if embedded is not None:
        if db.bind.dialect.name != "postgresql":
            raise ValueError("Vector retrieval requires PostgreSQL")
        vector_rows = list(
            db.scalars(
                base.where(
                    Passage.embedding.is_not(None), Passage.embedding_model == MODEL
                )
                .order_by(Passage.embedding.cosine_distance(embedded[0]), Passage.id)
                .limit(30)
            )
        )
    if mode == "vector":
        rows = vector_rows
    elif mode == "keyword":
        rows = keyword
    else:
        lookup = {p.id: p for p in [*keyword, *vector_rows]}
        rows = [
            lookup[i]
            for i in rrf([[p.id for p in keyword], [p.id for p in vector_rows]])
        ]
    available = embedded is not None and bool(vector_rows)
    return rows[:limit], {
        "mode": mode
        if available or mode == "keyword"
        else "keyword"
        if mode == "hybrid"
        else "vector_unavailable",
        "vector_available": available,
        "reason": embedder.detail,
    }


STOP = {
    "what",
    "which",
    "who",
    "the",
    "a",
    "an",
    "is",
    "are",
    "can",
    "does",
    "do",
    "to",
    "of",
    "for",
    "in",
    "and",
    "how",
    "with",
    "there",
    "under",
    "policy",
    "scheme",
    "this",
    "that",
    "be",
    "it",
    "must",
    "may",
    "should",
    "about",
}


def words(value):
    return {
        w
        for w in re.findall(r"[a-z0-9]+", value.lower())
        if w not in STOP and len(w) > 2
    }


def answer(db, question, policy, embedder, mode="hybrid"):
    passages, meta = retrieve(db, question, policy, embedder, mode)
    candidates = []
    anchors = words(question)
    for p in passages:
        for sentence in re.split(r"(?<=[.!?])\s+|\n", p.content):
            overlap = anchors & words(sentence)
            if anchors and len(overlap) / len(anchors) >= 0.6:
                candidates.append((len(overlap), p, sentence))
    if not candidates:
        return {
            "answer": "Policy evidence was insufficient to answer this question.",
            "supported": False,
            "citations": [],
            **meta,
            "retrieved_ids": [p.id for p in passages],
        }
    _, p, quote = max(candidates, key=lambda x: x[0])
    # When multiple revisions of one source overlap, a version-specific decision needs review.
    sources = [db.get(PolicyDocument, item[1].document_id) for item in candidates]
    if any(
        len({(d.id, d.version) for d in sources if d.source_url == url}) > 1
        for url in {d.source_url for d in sources}
    ):
        return {
            "answer": "Policy evidence was insufficient to answer this question.",
            "supported": False,
            "citations": [],
            **meta,
            "reason": "Conflicting effective versions need review",
            "retrieved_ids": [item.id for item in passages],
        }
    doc = db.get(PolicyDocument, p.document_id)
    # Extractive answer: no generated proposition can extend the cited passage.
    return {
        "answer": quote,
        "supported": True,
        "support_method": "extractive quote with lexical question coverage; requires human relevance review",
        "citations": [
            {
                "passage_id": p.id,
                "quote": quote,
                "start": p.content.index(quote),
                "end": p.content.index(quote) + len(quote),
                "title": doc.title,
                "section": p.section,
                "version": doc.version,
                "effective_date": doc.effective_date,
                "url": doc.source_url,
            }
        ],
        **meta,
        "retrieved_ids": [p.id for p in passages],
    }


def evaluate(db, labels, embedder):
    results = {}
    for mode in ("keyword", "vector", "hybrid"):
        rows = []
        for label in labels:
            policy = db.get(Policy, label["policy_id"])
            if not policy:
                raise ValueError("Unknown labeled policy version")
            response = answer(db, label["question"], policy, embedder, mode)
            relevant = set(label["relevant_passage_ids"])
            retrieved = set(response["retrieved_ids"][:5])
            recall = len(relevant & retrieved) / len(relevant) if relevant else None
            citation_ids = {c["passage_id"] for c in response["citations"]}
            support = bool(citation_ids) and citation_ids <= set(
                label.get("supporting_passage_ids", label["relevant_passage_ids"])
            )
            rows.append(
                {
                    "question_id": label["id"],
                    "recall_at_5": recall,
                    "citation_supported_by_labels": support
                    if response["supported"]
                    else None,
                    "abstained": not response["supported"],
                    "correct_abstention": not response["supported"]
                    if not relevant
                    else None,
                    "vector_available": response["vector_available"],
                }
            )
        eligible = [r["recall_at_5"] for r in rows if r["recall_at_5"] is not None]
        runnable = mode == "keyword" or all(r["vector_available"] for r in rows)
        results[mode] = {
            "status": "completed" if runnable else "not_run_vector_unavailable",
            "recall_at_5": sum(eligible) / len(eligible)
            if eligible and runnable
            else None,
            "questions": rows,
        }
    return {
        "question_count": len(labels),
        "methods": results,
        "note": "Same labeled questions, policy-version filter and top five cutoff. No-answer questions are excluded from mean Recall@5 and evaluated for abstention.",
    }
