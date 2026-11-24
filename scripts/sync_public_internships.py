"""Refresh the configured public internship sources in PostgreSQL."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import database
from app.public_feed import sync

if __name__ == "__main__":
    engine, session = database(os.environ["DATABASE_URL"])
    try:
        report = sync(session)
        print(json.dumps(report, indent=2))
        if not all(board["board_fetched"] for board in report):
            sys.exit(1)
    finally:
        engine.dispose()
