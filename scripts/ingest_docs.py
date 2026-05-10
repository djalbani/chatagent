#!/usr/bin/env python3
"""
Batch document ingestion CLI.

Usage:
    python scripts/ingest_docs.py path/to/doc.pdf
    python scripts/ingest_docs.py docs/ --source "Product Manual"
    python scripts/ingest_docs.py docs/ --api-url http://localhost:8000

Options:
    --api-url   Backend base URL (default: http://localhost:8000)
    --source    Override the source name stored in the knowledge base
    --recursive Walk directories recursively (default: True)
"""

import argparse
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed.  Run: pip install requests")
    sys.exit(1)

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".rst"}


def ingest_file(path: Path, api_url: str, source_name: str | None) -> dict:
    """POST a single file to /ingest and return the JSON response."""
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "application/octet-stream")}
        data = {"source_name": source_name or path.name} if source_name else {}
        resp = requests.post(f"{api_url}/ingest", files=files, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def collect_files(targets: list[Path], recursive: bool) -> list[Path]:
    found = []
    for t in targets:
        if t.is_file():
            if t.suffix.lower() in SUPPORTED:
                found.append(t)
            else:
                print(f"  skip  {t}  (unsupported type)")
        elif t.is_dir():
            pattern = "**/*" if recursive else "*"
            for p in sorted(t.glob(pattern)):
                if p.is_file() and p.suffix.lower() in SUPPORTED:
                    found.append(p)
        else:
            print(f"  skip  {t}  (not found)")
    return found


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the support agent knowledge base.")
    parser.add_argument("paths", nargs="+", help="Files or directories to ingest")
    parser.add_argument("--api-url", default="http://localhost:8000", metavar="URL")
    parser.add_argument("--source", default=None, metavar="NAME",
                        help="Source label stored in the knowledge base (defaults to filename)")
    parser.add_argument("--no-recursive", action="store_true",
                        help="Do not recurse into sub-directories")
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")

    # Health check
    try:
        r = requests.get(f"{api_url}/health", timeout=10)
        r.raise_for_status()
        info = r.json()
        print(f"Connected to {info.get('bot', '?')} at {api_url}")
        print(f"Knowledge base currently has {info.get('chunks_indexed', '?')} chunks\n")
    except Exception as e:
        print(f"ERROR: Cannot reach backend at {api_url}: {e}")
        sys.exit(1)

    targets = [Path(p) for p in args.paths]
    files = collect_files(targets, recursive=not args.no_recursive)

    if not files:
        print("No supported files found.")
        sys.exit(0)

    print(f"Found {len(files)} file(s) to ingest:\n")

    ok = fail = 0
    for path in files:
        label = args.source or path.name
        try:
            result = ingest_file(path, api_url, args.source)
            chunks = result.get("chunks_added", "?")
            total = result.get("total_chunks", "?")
            print(f"  [OK]   {path.name:40s}  -> {chunks:>4} chunks  (total: {total})")
            ok += 1
        except requests.HTTPError as e:
            msg = ""
            try:
                msg = e.response.json().get("detail", "")
            except Exception:
                pass
            print(f"  [FAIL] {path.name:40s}  -> HTTP {e.response.status_code}: {msg or e}")
            fail += 1
        except Exception as e:
            print(f"  [FAIL] {path.name:40s}  -> {e}")
            fail += 1

    print(f"\nDone: {ok} succeeded, {fail} failed.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
