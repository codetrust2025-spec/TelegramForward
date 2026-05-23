#!/usr/bin/env python3
"""Remove invalid (username not found) groups from master list and legacy files."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# account1 dead export — INVALID (username not found)
INVALID_GROUPS = [
    "JobGroupAmerica", "RemoteJavaJobs", "RemoteNodeJobs", "RemotePythonJobs",
    "RemoteReactJobs", "SalesforceJobs", "TestingJobs", "agilejobs",
    "angular_developers_jobs", "aws_cloud_jobs", "azurecloudjobs", "bigdatajobs",
    "blockchainjobs", "cloudcomputingjobs", "contractjobsindia", "dailyjobupdates",
    "dataengineerjobs", "datawarehousejobs", "devops_engineer_jobs",
    "django_developer_jobs", "ethicalhackingjobs", "experiencedjobsindia",
    "flutterdeveloperjobs", "fresherjobsindia", "frontendjobsindia",
    "fullstackdeveloperjobsindia", "gamedeveloperjobs", "golangjobsindia",
    "hiringdevelopersindia", "hiringengineersindia", "hiringexperiencedindia",
    "hiringfreshersindia", "hiringitindia", "hiringnowindia", "hiringremotelyindia",
    "homebasedjobsindia", "hrjobsindia", "internationaljobsindia", "itjobsinindia",
    "java_jobs_india", "javascriptdeveloperjobs", "jobalertsindia", "jobcommunityindia",
    "jobconsultancyindia", "jobsearchindia", "mernstackdeveloperjobs",
    "microservicesdeveloperjobs", "mncjobsindia", "mobileappdeveloperjobs",
    "nodejs_jobs_india", "nontechjobsindia", "offcampusjobs", "onlinejobsindia",
    "overseasjobsindia", "peoplesoftjobs", "productmanagerjobs", "projectmanagerjobs",
    "qaautomationjobs", "react_jobs_india", "remoteangularjobs", "remoteawsjobs",
    "remotebackendjobs", "remotecloudjobs", "remotedevopsjobs", "remoteflutterjobs",
    "remotejavajobsindia", "remotejavascriptjobs", "remotemernjobs",
    "remotenodejobsindia", "remotepythonjobsindia", "remotereactnativejobs",
    "remotetestingjobs", "remoteuiuxjobs", "remotewebdeveloperjobs", "sapjobsindia",
    "seleniumjobs", "servicenowjobs", "sqljobs", "startuphiringindia",
    "startupjobsindia", "techjobsindia", "uiuxjobsindia", "unstopgroupexam",
    "walkinjobsindia", "webdeveloperjobsindia", "wfhjobsindia",
]


def _norm(name: str) -> str:
    return (name or "").strip().lstrip("@").lower()


def main() -> int:
    from core.config import ACCOUNTS, GROUPS_FILE, BASE_DIR, STATE_DIR
    from core.groups_store import load_master_groups, save_master_groups, load_account_dead, save_account_dead

    remove_set = {_norm(g) for g in INVALID_GROUPS}
    master = load_master_groups()
    before = len(master)
    kept = [g for g in master if _norm(g) not in remove_set]
    removed = before - len(kept)
    save_master_groups(kept)

    # Legacy txt/json at project root if present
    for path in (
        os.path.join(BASE_DIR, "groups_list.json"),
        os.path.join(BASE_DIR, "groups_list.txt"),
    ):
        if not os.path.exists(path):
            continue
        if path.endswith(".json"):
            import json
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    pruned = [g for g in data if _norm(g) not in remove_set]
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(pruned, f, indent=2)
                    print(f"  pruned {path}: {len(data)} -> {len(pruned)}")
            except Exception as e:
                print(f"  skip {path}: {e}")

    # Drop removed names from per-account invalid lists (redundant entries)
    for slot in ACCOUNTS:
        invalid, blocked = load_account_dead(slot)
        new_invalid = {g for g in invalid if _norm(g) not in remove_set}
        if new_invalid != invalid:
            save_account_dead(slot, new_invalid, blocked)
        intel_path = os.path.join(STATE_DIR, slot, "group_intelligence.json")
        if os.path.exists(intel_path):
            import json
            try:
                with open(intel_path, encoding="utf-8") as f:
                    raw = json.load(f)
                groups = raw.get("groups") if isinstance(raw, dict) else None
                if isinstance(groups, dict):
                    pruned_g = {k: v for k, v in groups.items() if _norm(k) not in remove_set}
                    if len(pruned_g) != len(groups):
                        raw["groups"] = pruned_g
                        with open(intel_path, "w", encoding="utf-8") as f:
                            json.dump(raw, f, indent=2)
                        print(f"  {slot} intelligence: {len(groups)} -> {len(pruned_g)} groups")
            except Exception as e:
                print(f"  skip {slot} intelligence: {e}")

    print(f"Master list: {before} -> {len(kept)} (removed {removed} invalid usernames)")
    print(f"Saved: {GROUPS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
