"""Persistent isolated Chatterbox synthesis worker.

Protocol: one JSON object per line on stdin/stdout. Diagnostic output goes to
stderr so it cannot corrupt the protocol stream.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback
import unicodedata


def send(payload: dict[str, object]) -> None:
    """Write one UTF-8 JSON response without using the Windows console code page."""

    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def extract_text(request: dict[str, object]) -> str:
    """Return normalized synthesis text and reject non-string protocol values."""

    value = request.get("text")
    if not isinstance(value, str):
        raise TypeError(f"Synthesis text must be str, got {type(value).__name__}")
    # Force a plain built-in str and stable Unicode representation for tokenizers.
    text = unicodedata.normalize("NFC", value).strip()
    if not text:
        raise ValueError("Synthesis text is empty")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--language", default="el")
    parser.add_argument("--reference-audio")
    args = parser.parse_args()

    try:
        with redirect_stdout(sys.stderr):
            import torchaudio as ta
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            print(f"Loading Chatterbox Multilingual on {args.device}", file=sys.stderr, flush=True)
            model = ChatterboxMultilingualTTS.from_pretrained(device=args.device)
        print("Chatterbox model loaded", file=sys.stderr, flush=True)
    except Exception as exc:
        send({"status": "error", "error": f"Worker startup failed: {exc}"})
        traceback.print_exc(file=sys.stderr)
        return 1

    send({"status": "ready", "device": args.device})

    # Read bytes explicitly. Windows may otherwise decode UTF-8 requests through
    # the active console code page (for example cp1253), corrupting Greek text.
    for raw_bytes in sys.stdin.buffer:
        try:
            raw = raw_bytes.decode("utf-8")
            request = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            send({"status": "error", "error": f"Invalid UTF-8 JSON: {exc}"})
            continue
        if request.get("command") == "shutdown":
            return 0
        request_id = request.get("id")
        if request.get("command") != "synthesize":
            send({"id": request_id, "status": "error", "error": "Unknown command"})
            continue

        try:
            text = extract_text(request)
            output_path = Path(str(request["output_path"]))
            kwargs: dict[str, str] = {"language_id": args.language}
            if args.reference_audio:
                reference = Path(args.reference_audio)
                if not reference.is_file():
                    raise FileNotFoundError(f"Voice reference not found: {reference}")
                kwargs["audio_prompt_path"] = str(reference)
            with redirect_stdout(sys.stderr):
                wav = model.generate(text, **kwargs)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                ta.save(str(output_path), wav.cpu(), model.sr)
            send({"id": request_id, "status": "ok", "bytes": output_path.stat().st_size})
        except Exception as exc:
            send({"id": request_id, "status": "error", "error": str(exc)})
            traceback.print_exc(file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
