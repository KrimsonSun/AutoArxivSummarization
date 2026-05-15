"""Identify and (optionally) delete failed eval JSONs so strict_reeval retries.

Failure patterns we sweep:
  1. error stub: {"error": True, ...}            — verifier/extractor exception
  2. recall=0 + precision>0 + hal>0              — recall_checker failed
  3. precision=0 + hal=1                          — verifier failed on every claim
  4. method == 'Ours_onevision_v3.voting'         — script bug, voting transcript
                                                     mistakenly treated as a summary

Usage:
  python -m experiment.sweep_failed_evals [--dry-run] [--also-clean-voting]
"""
import argparse
import json
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1] / "outputs" / "experiment"


def classify(eval_path: Path) -> str | None:
    try:
        d = json.loads(eval_path.read_text())
    except Exception:
        return "unparseable"
    if d.get("error"):
        return "error_stub"
    p = d.get("evidence_coverage", -1)
    r = d.get("paper_recall", -1)
    h = d.get("hallucination_rate", -1)
    f1 = d.get("f1", -1)
    # Hard failure: full recall_checker fallback
    if r == 0.0 and p > 0.0 and (h is not None) and h >= 0:
        # could be legitimate (zero coverage), but if precision is high
        # and there ARE claims, likely a recall_checker fail.
        if d.get("total_claims", 0) > 5 and f1 == 0.0:
            return "recall_zero_likely_failure"
    # Verifier failed on every claim
    if p == 0.0 and h == 1.0 and d.get("total_claims", 0) > 5:
        return "precision_zero_verifier_fail"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print, don't delete.")
    parser.add_argument("--also-clean-voting", action="store_true",
                        help="Also delete voting.json eval stubs.")
    parser.add_argument("--mode", choices=["strict", "deberta", "both"], default="both")
    args = parser.parse_args()

    dirs = []
    if args.mode in ("strict", "both"):
        dirs.append(EVAL_ROOT / "evals_strict")
    if args.mode in ("deberta", "both"):
        dirs.append(EVAL_ROOT / "evals_deberta")

    swept: dict[str, int] = {}
    for d in dirs:
        if not d.exists():
            continue
        for p in d.rglob("*.eval.json"):
            method = p.stem.replace(".eval", "")
            if "voting" in method and args.also_clean_voting:
                if not args.dry_run:
                    p.unlink()
                swept["voting_pollution"] = swept.get("voting_pollution", 0) + 1
                continue
            cat = classify(p)
            if cat:
                if not args.dry_run:
                    p.unlink()
                swept[cat] = swept.get(cat, 0) + 1
                rel = p.relative_to(EVAL_ROOT)
                print(f"  {'(dry)' if args.dry_run else 'rm'} {rel}  [{cat}]")
    print()
    print("Summary:")
    for k, v in sorted(swept.items()):
        print(f"  {k}: {v}")
    print()
    if args.dry_run:
        print("(dry run — re-run without --dry-run to actually delete)")
    else:
        print("Re-run strict_reeval / deberta evals to refill the deleted entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
