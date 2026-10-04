"""Load the fictional student and the two scoped UK undergraduate CS programmes."""

import json
from copy import deepcopy
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROGRAMMES = json.loads((DATA_DIR / "programmes.json").read_text(encoding="utf-8"))


def list_programmes():
    return [deepcopy(item) for item in PROGRAMMES]


def load_case(program_id="manchester_cs_ug"):
    programme = next((p for p in PROGRAMMES if p["id"] == program_id), None)
    if programme is None:
        raise ValueError("仅支持已收录的英国本科 CS 项目")
    case = json.loads((DATA_DIR / "demo_case.json").read_text(encoding="utf-8"))
    case["programme"] = deepcopy(programme)
    return case
