"""Verify a graph interrupt survives an API restart on explicitly disposable PostgreSQL.

Prepare creates isolated fixtures. Restart the API without clearing its database, then check.
Do not point this command at a participant installation.
"""
import argparse
from datetime import date
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("stage", choices=["prepare", "check"])
parser.add_argument("--base", required=True)
parser.add_argument("--receipt", type=Path, required=True)
parser.add_argument("--isolated", action="store_true", required=True)
args = parser.parse_args()
if httpx.URL(args.base).host not in ("localhost", "127.0.0.1", "::1"):
    parser.error("Run only against an isolated loopback installation")

with httpx.Client(base_url=args.base.rstrip("/") + "/api", timeout=30) as client:
    def call(method, endpoint, body=None, token=None, expected=200):
        response = client.request(method, endpoint, json=body,
                                  headers={"Authorization": f"Bearer {token}"} if token else None)
        if response.status_code != expected:
            raise RuntimeError(f"{method} {endpoint} returned {response.status_code}")
        return response.json()

    health = call("GET","/health")
    assert health["database"] == "postgresql" and health["checkpoints"] == "postgresql", health
    assert health["fixture_mode"], "The restart check does not use any model provider"
    admin = call("POST","/auth/login",{
        "email":os.getenv("ADMIN_EMAIL","admin@allocate.local"),"password":os.environ["ADMIN_PASSWORD"],
    })["access_token"]
    if args.stage == "prepare":
        nonce = uuid4().hex[:10]
        email = f"restart-{nonce}@unit.test"
        password = uuid4().hex
        user = call("POST", "/auth/register", {"email":email,"name":"Isolated checkpoint test","password":password}, expected=201)
        applicant = call("POST","/auth/login",{"email":email,"password":password})["access_token"]
        call("PUT","/applicant/profile",{"consent": True},applicant)
        today = date.today().isoformat()
        scope = "Isolated checkpoint test " + nonce
        lid = call("POST","/import/listings/commit",[{
            "title":"Isolated checkpoint test role", "organization":scope, "source_name":"Isolated fixture",
            "source_url":f"https://unit.test/checkpoint-{nonce}", "last_verified":today, "status":"open",
            "rolling":True, "description":"Completed BTech degree required for isolated test.",
            "mandatory_qualifications":["BTech"],
        }], admin, expected=201)["ids"][0]
        call("POST",f"/admin/listings/{lid}/approve",{"expected_version":1,"verification_reference":"Isolated restart test"},admin)
        pid = call("POST","/admin/policies",{"name":scope,"config":{
            "coverage_confirmed":True,"scheme":scope,"effective_date":today,
        }},admin)["id"]
        call("POST",f"/admin/policies/{pid}/approve",token=admin)
        rid = call("POST","/admin/rounds",{"name":scope,"scope":scope,"policy_id":pid,"listing_ids":[lid]},admin)["id"]
        body={"applicant_id":user["id"],"evidence_reference":"Isolated restart participant"}
        call("PUT",f"/admin/rounds/{rid}/participation",body,admin)
        call("PUT",f"/rounds/{rid}/choices",{"listing_ids":[lid]},applicant)
        claim = call("POST","/applicant/evidence",{
            "kind":"qualification","value":"BTech","excerpt":"Completed BTech degree in 2025.","context":"education",
        },applicant)
        case = call("POST","/agent/cases",{"round_id":rid},applicant)
        assert case["status"] == "needs_review" and case["next_nodes"] == ["review"], case
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps({"case":case["id"],"claim":claim["id"]}),encoding="utf-8")
        print("Case paused in PostgreSQL. Restart the API and run the check stage.")
    else:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        case = call("GET",f"/agent/cases/{receipt['case']}",token=admin)
        assert case["status"] == "needs_review" and case["next_nodes"] == ["review"], case
        call("POST",f"/admin/evidence/{receipt['claim']}/review",{"status":"verified"},admin)
        case = call("POST",f"/admin/agent/cases/{receipt['case']}/resume",token=admin)
        assert case["status"] == "ready" and not case["next_nodes"], case
        print("The same checkpoint resumed to ready after the API restart.")
