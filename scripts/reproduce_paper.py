"""Reproduce AllocateAI paper Section VII. No database or application records."""

from collections import Counter
from itertools import product
from pathlib import Path
import argparse
import csv
import json
import platform

import ortools
from ortools.sat.python import cp_model

EDGES = list(product(range(3), repeat=2))
ORACLE = [
    tuple((a, r) for a, r in enumerate(roles) if r != -1)
    for roles in product(range(-1, 3), repeat=3)
    if len([r for r in roles if r != -1]) == len({r for r in roles if r != -1})
]


def objective(pairs, ranks):
    return len(pairs), sum(4 - ranks[e] for e in pairs)


def experiment():
    assert len(ORACLE) == 34
    results = []
    for mask in range(512):
        allowed = {e for bit, e in enumerate(EDGES) if mask & (1 << bit)}
        ranks = {
            e: rank
            for a in range(3)
            for rank, e in enumerate(sorted(e for e in allowed if e[0] == a), 1)
        }
        model = cp_model.CpModel()
        x = {e: model.new_bool_var(f"x_{e[0]}_{e[1]}") for e in sorted(allowed)}
        for index in range(3):
            model.add(sum(v for e, v in x.items() if e[0] == index) <= 1)
            model.add(sum(v for e, v in x.items() if e[1] == index) <= 1)
        model.maximize(sum((14 - ranks[e]) * v for e, v in x.items()))
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 33
        assert solver.solve(model) == cp_model.OPTIMAL, mask
        exact = [e for e in x if solver.value(x[e])]
        used = set()
        greedy = []
        for a in range(3):
            acceptable = [
                (a, r) for r in range(3) if (a, r) in allowed and r not in used
            ]
            if acceptable:
                greedy.append(acceptable[0])
                used.add(acceptable[0][1])
        assert set(exact) <= allowed and len({e[0] for e in exact}) == len(
            {e[1] for e in exact}
        ) == len(exact)
        n, u = objective(exact, ranks)
        ng, ug = objective(greedy, ranks)
        oracle = max(objective(p, ranks) for p in ORACLE if set(p) <= allowed)
        assert (n, u) == oracle, (mask, n, u, oracle)
        assert n - ng in (0, 1) and (n, u) >= (ng, ug), mask
        results.append(
            {
                "mask": mask,
                "edges": len(allowed),
                "cp_sat_n": n,
                "cp_sat_utility": u,
                "oracle_n": oracle[0],
                "oracle_utility": oracle[1],
                "greedy_n": ng,
                "greedy_utility": ug,
                "classification": "count loss"
                if n > ng
                else "utility loss"
                if u > ug
                else "tie",
            }
        )
    counts = Counter(r["classification"] for r in results)
    summary = {
        "patterns": len(results),
        "oracle_agreement": len(results),
        "feasible": len(results),
        "greedy_count_loss": counts["count loss"],
        "greedy_utility_loss": counts["utility loss"],
        "ties": counts["tie"],
        "cp_sat_assignments": sum(r["cp_sat_n"] for r in results),
        "greedy_assignments": sum(r["greedy_n"] for r in results),
        "cp_sat_full": sum(r["cp_sat_n"] == 3 for r in results),
        "greedy_full": sum(r["greedy_n"] == 3 for r in results),
    }
    expected = dict(zip(summary, (512, 512, 512, 95, 14, 403, 1236, 1141, 247, 168)))
    assert summary == expected, {"measured": summary, "paper": expected}
    return summary, results


def chart(out, results):
    # SVG with programmatically generated plot marks. No plotting dependency.
    cols = [sum(r["edges"] == j for r in results) for j in range(10)]
    losses = [
        sum(r["edges"] == j and r["classification"] == "count loss" for r in results)
        for j in range(10)
    ]
    header = '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="365" viewBox="0 0 720 365" role="img">'
    base = [header, '<rect width="720" height="365" fill="white"/>']

    def label(x, y, value, size=14):
        return f'<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="{size}" fill="#152632">{value}</text>'

    for title, name, denominator, series, limit, x_label in (
        (
            "Greedy cardinality shortfall by edge count",
            "greedy-shortfall.svg",
            cols,
            [[100 * l / n for l, n in zip(losses, cols)]],
            40,
            "Admissible edges (number of cases in parentheses)",
        ),
        (
            "Distribution of assignment count",
            "assignment-count.svg",
            [None] * 4,
            [
                [sum(r[k] == j for r in results) for j in range(4)]
                for k in ("greedy_n", "cp_sat_n")
            ],
            300,
            "Assignments per case",
        ),
    ):
        draw = list(base)
        draw.append(label(360, 28, title, 20))
        draw.append(label(360, 51, "Isolated 3 × 3 solver cases", 12))
        for n in range(5):
            y = 305 - n * 56
            draw.append(f'<path d="M66 {y} H700" stroke="#d2dce2"/>')
            draw.append(
                label(
                    40,
                    y + 4,
                    f"{limit * n / 4:g}%" if limit == 40 else f"{limit * n / 4:g}",
                    12,
                )
            )
        stride = 630 / len(denominator)
        for j, n in enumerate(denominator):
            center = 66 + (j + 0.5) * stride
            draw.append(label(center, 324, str(j) if n is None else f"{j} ({n})", 12))
            width = min(38, stride / (len(series) + 1))
            for k, values in enumerate(series):
                v = values[j]
                h = v / limit * 224
                x = center + (k - len(series) / 2) * width
                col = ("#1a708b", "#753f51")[k]
                draw.append(
                    f'<rect x="{x:g}" y="{305 - h:g}" width="{width - 2:g}" height="{h:g}" fill="{col}"/>'
                )
                if v:
                    draw.append(
                        label(
                            x + (width - 2) / 2,
                            299 - h,
                            f"{v:.1f}" if limit == 40 else str(v),
                            12,
                        )
                    )
        draw.append(label(382, 350, x_label, 13))
        if len(series) == 2:
            draw.append(
                '<rect x="500" y="62" width="12" height="12" fill="#1a708b"/><rect x="599" y="62" width="12" height="12" fill="#753f51"/>'
            )
            draw.extend([label(542, 73, "Greedy", 12), label(642, 73, "CP-SAT", 12)])
        (out / name).write_text("\n".join(draw + ["</svg>"]), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    summary, rows = experiment()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = {
        "data": "isolated abstract graph patterns",
        "python": platform.python_version(),
        "ortools": ortools.__version__,
        "summary": summary,
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    chart(output, rows)
    print(json.dumps(result, indent=2))
