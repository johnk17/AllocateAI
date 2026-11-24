"""Convert an official ESCO CSV or O*NET TSV/ZIP to the admin import contract."""

import argparse, csv, io, json, zipfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("input")
p.add_argument("--source", choices=["ESCO", "O*NET"], required=True)
p.add_argument("--version", required=True)
p.add_argument("--output", required=True)
args = p.parse_args()
path = Path(args.input)
if path.suffix == ".zip":
    with zipfile.ZipFile(path) as z:
        candidates = [
            n
            for n in z.namelist()
            if n.endswith("Technology Skills.txt") or n.endswith("skills_en.csv")
        ]
        if len(candidates) != 1:
            raise SystemExit(
                "Select an archive with one Technology Skills.txt or skills_en.csv file"
            )
        data = z.read(candidates[0]).decode("utf-8-sig")
else:
    data = path.read_text(encoding="utf-8-sig")
rows = list(
    csv.DictReader(io.StringIO(data), delimiter="\t" if args.source == "O*NET" else ",")
)
if args.source == "O*NET":
    seen = set()
    unique = []
    for row in rows:
        key = (row.get("Commodity Code"), row.get("Example"))
        if key not in seen:
            unique.append(row)
            seen.add(key)
    rows = unique
Path(args.output).write_text(
    json.dumps(
        {"source": args.source, "version": args.version, "rows": rows},
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"Converted {len(rows)} source records; no applicant data included.")
