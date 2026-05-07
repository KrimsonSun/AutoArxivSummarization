"""Generate TypeScript .d.ts from Pydantic schemas (handoff §13.3).

Run:  python scripts/export_types.py [output_path]

Default output: ../typescript-main-project/types/summarizer.d.ts (relative
to this project root). Pass an explicit path to override.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic2ts import generate_typescript_defs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT.parent / "src" / "types" / "summarizer.d.ts"


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    generate_typescript_defs(
        "src.schemas.summary",
        str(out_path),
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
