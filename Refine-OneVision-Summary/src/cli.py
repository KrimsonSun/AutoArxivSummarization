"""CLI entry point (handoff §13.1).

Contract:
-   Final FinalSummary JSON → stdout (parent TS process consumes it).
-   ALL logs / progress / warnings → stderr.
-   Exit codes:
        0 = success
        1 = configuration error (missing key, bad config)
        2 = PDF parsing failure
        3 = LLM call failure (after retries)
        4 = schema validation failure
        5 = pipeline failure (other)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from src.config.loader import PipelineConfig, load_config
from src.config.settings import ConfigurationError
from src.llm_clients.base import LLMError
from src.pipeline import OneVisionPipeline, PipelineError
from src.postprocessing.markdown_formatter import to_markdown
from src.preprocessing.pdf_parser import parse_pdf  # noqa: F401  (imported eagerly)
from src.schemas.summary import FinalSummary
from src.utils.logging import configure_logging, get_logger

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_PDF = 2
EXIT_LLM = 3
EXIT_SCHEMA = 4
EXIT_OTHER = 5


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RefinedSummarization — Multi-Agent Debate Summarizer"
    )
    parser.add_argument("--pdf", required=True, help="Path to the PDF file.")
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument(
        "--output-format",
        choices=["json", "markdown", "both"],
        default="json",
        help="What to write to stdout (logs always go to stderr).",
    )
    parser.add_argument(
        "--skip-healthcheck",
        action="store_true",
        help="Skip the LLM ping at startup (CI-friendly).",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Also write outputs/{json,markdown}/<arxiv_id>.{json,md} per config.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=(
            "Path to write the FinalSummary JSON to. If set, also writes "
            "<out>.voting.json with the full voting transcript. Stdout is "
            "suppressed so logs don't contaminate the file."
        ),
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Config load failed: {e}", file=sys.stderr)
        sys.exit(EXIT_CONFIG)

    configure_logging(level=config.logging.level, json_logs=config.logging.json_logs)
    log = get_logger("cli")

    try:
        pipeline = OneVisionPipeline(config)
    except ConfigurationError as e:
        log.error("config_error", err=str(e))
        sys.exit(EXIT_CONFIG)

    if not args.skip_healthcheck:
        log.info("running_healthcheck")
        try:
            results = asyncio.run(pipeline.healthcheck())
        except LLMError as e:
            log.error("healthcheck_failed", err=str(e))
            sys.exit(EXIT_CONFIG)
        if not all(results.values()):
            log.error("healthcheck_failed", results=results)
            sys.exit(EXIT_CONFIG)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        log.error("pdf_missing", path=str(pdf_path))
        sys.exit(EXIT_PDF)

    try:
        result, voting_transcript = asyncio.run(pipeline.run(pdf_path))
    except PipelineError as e:
        log.error("pipeline_error", err=str(e))
        sys.exit(EXIT_OTHER)
    except LLMError as e:
        log.error("llm_error", err=str(e))
        sys.exit(EXIT_LLM)
    except FileNotFoundError as e:
        log.error("pdf_error", err=str(e))
        sys.exit(EXIT_PDF)
    except Exception as e:  # last-resort safety net
        log.error("unexpected", err=str(e), type=type(e).__name__)
        sys.exit(EXIT_OTHER)

    # Save to disk if requested.
    if args.save:
        _save_outputs(result, config)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.model_dump_json(indent=2))
        voting_path = out_path.with_suffix(out_path.suffix + ".voting.json") \
            if not out_path.name.endswith(".voting.json") \
            else out_path
        # Use sibling .voting.json filename: foo.json → foo.voting.json
        if out_path.suffix == ".json":
            voting_path = out_path.with_name(out_path.stem + ".voting.json")
        voting_path.write_text(voting_transcript.model_dump_json(indent=2))
        log.info("written", out=str(out_path), voting_out=str(voting_path))
        sys.exit(EXIT_OK)

    # stdout: per --output-format.
    if args.output_format == "json":
        sys.stdout.write(result.model_dump_json(indent=2))
    elif args.output_format == "markdown":
        sys.stdout.write(to_markdown(result))
    else:  # both — JSON first, markdown after a delimiter
        sys.stdout.write(result.model_dump_json(indent=2))
        sys.stdout.write("\n\n---MARKDOWN---\n\n")
        sys.stdout.write(to_markdown(result))
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(EXIT_OK)


def _save_outputs(result: FinalSummary, config: PipelineConfig) -> None:
    project_root = Path(__file__).resolve().parents[1]
    json_dir = project_root / config.output.json_output_dir
    json_dir.mkdir(parents=True, exist_ok=True)
    fname = result.metadata.arxiv_id or "paper"
    (json_dir / f"{fname}.json").write_text(result.model_dump_json(indent=2))
    if config.output.emit_markdown:
        md_dir = project_root / config.output.markdown_output_dir
        md_dir.mkdir(parents=True, exist_ok=True)
        (md_dir / f"{fname}.md").write_text(to_markdown(result))


if __name__ == "__main__":
    main()
