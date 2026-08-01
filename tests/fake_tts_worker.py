"""Tiny JSON-line worker used by TTS subprocess tests."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--device")
parser.add_argument("--language")
parser.add_argument("--reference-audio")
parser.parse_args()
print(json.dumps({"status": "ready"}), flush=True)
for raw in sys.stdin:
    request = json.loads(raw)
    if request.get("command") == "shutdown":
        break
    path = Path(request["output_path"])
    path.write_bytes(b"RIFF-worker-wave")
    print(json.dumps({"id": request["id"], "status": "ok"}), flush=True)
