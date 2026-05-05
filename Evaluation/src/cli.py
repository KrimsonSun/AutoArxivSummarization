"""CLI entry — usage:

    python -m src.cli \
        --summary outputs/<id>.json    # FinalSummary JSON, .md, or .txt
        --paper   path/to/paper.pdf    # PDF or PaperBundle.json
        --output  evaluations/<id>.json   # where to write the report

Stdout = the EvaluationReport JSON (so it pipes nicely).
Stderr = structured logs.

Exit codes:  0=ok  1=config  2=input  3=llm  5=other
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.config_loader import load_config
from src.llm_client import LLMError
from src.logging import configure, get_logger
from src.pipeline import EvaluationPipeline
from src.settings import ConfigurationError

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_INPUT = 2
EXIT_LLM = 3
EXIT_OTHER = 5


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coverage + Hallucination evaluator (4-step claim verification)"
    )
    parser.add_argument("--summary", required=True, help="FinalSummary JSON / .md / .txt path")
    parser.add_argument("--paper", required=True, help="Paper PDF or PaperBundle JSON path")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--output", default="-", help="Path to write the report JSON. '-' = stdout.")
    parser.add_argument("--skip-healthcheck", action="store_true")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Config load failed: {e}", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    configure(level=config.logging.level, json_logs=config.logging.json_logs)
    log = get_logger("cli")

    try:
        pipeline = EvaluationPipeline(config)
    except ConfigurationError as e:
        log.error("config_error", err=str(e))
        sys.exit(EXIT_CONFIG)

    if not args.skip_healthcheck:
        try:
            ok = asyncio.run(pipeline.healthcheck())
            if not ok:
                log.error("healthcheck_failed")
                sys.exit(EXIT_CONFIG)
        except LLMError as e:
            log.error("healthcheck_error", err=str(e))
            sys.exit(EXIT_CONFIG)

    summary_path = Path(args.summary)
    paper_path = Path(args.paper)
    if not summary_path.exists():
        log.error("summary_missing", path=str(summary_path))
        sys.exit(EXIT_INPUT)
    if not paper_path.exists():
        log.error("paper_missing", path=str(paper_path))
        sys.exit(EXIT_INPUT)

    try:
        report = asyncio.run(pipeline.run(summary_path, paper_path))
    except LLMError as e:
        log.error("llm_error", err=str(e))
        sys.exit(EXIT_LLM)
    except FileNotFoundError as e:
        log.error("input_error", err=str(e))
        sys.exit(EXIT_INPUT)
    except Exception as e:
        log.error("unexpected", err=str(e), type=type(e).__name__)
        sys.exit(EXIT_OTHER)

    body = report.model_dump_json(indent=2)
    if args.output == "-":
        sys.stdout.write(body + "\n")
        sys.stdout.flush()
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body)
        log.info("report_written", path=str(out_path))

    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
