"""Offline replay: take the n=5 smoke transcripts and re-score with Fix 3.

The Fix 1+2 smoke run already wrote per-draft missing_info / factual_error /
unsupported_claim / total counts to reports/voter_ab_smoke/<id>.json.
Fix 3 changes the voter's scoring rule from density to absolute missing_info,
which is deterministic given those counts. So we can simulate the new
voter's winner choice without burning more API credit.

Outputs the predicted winner per paper and the aggregate distribution.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
RPT = ROOT / "reports" / "voter_ab_smoke"


def fix3_winner(scores: list[dict]) -> tuple[str, str, str]:
    """Apply Fix-3 scoring: argmin missing_info, tie-break by precision penalty.

    Returns (winner_label, winner_agent_id, reason).
    """
    keyed = []
    for s in scores:
        precision_penalty = s["n_factual_error"] + s["n_unsupported_claim"]
        keyed.append((
            s["n_missing_info"],
            precision_penalty,
            s["n_total_issues"],
            s["draft_label"],
            s,
        ))
    keyed.sort()
    winner = keyed[0][4]
    # Detect ties on the primary signal.
    primary_winners = [k for k in keyed if k[0] == keyed[0][0]]
    reason = "clean win"
    if len(primary_winners) > 1:
        # Did precision penalty break the tie?
        same_pp = [k for k in primary_winners if k[1] == keyed[0][1]]
        if len(same_pp) > 1:
            reason = f"degenerate tie ({len(same_pp)}-way), broke by label"
        else:
            reason = "tie on missing_info, broken by precision penalty"
    return winner["draft_label"], winner["agent_id"], reason


def main() -> None:
    files = sorted(RPT.glob("[12]*.json"))
    print(f"Replaying Fix 3 over {len(files)} smoke papers ({RPT.name}).\n")
    print("=" * 92)
    new_winners: dict[str, int] = {}
    old_winners: dict[str, int] = {}

    for f in files:
        r = json.load(f.open())
        aid = r["arxiv_id"]
        cg = r["results"].get("claim_grounding", {})
        scores = cg.get("claim_grounding_scores") or []
        if not scores:
            continue
        old_winner = cg.get("winner_agent_id", "?")
        old_winners[old_winner] = old_winners.get(old_winner, 0) + 1
        new_label, new_agent, reason = fix3_winner(scores)
        new_winners[new_agent] = new_winners.get(new_agent, 0) + 1
        flip = " ⇄ FLIPPED" if new_agent != old_winner else ""
        print(f"\n{aid}")
        print(f"  per-draft (label, agent, words, total, missing, factual+unsup):")
        for s in scores:
            pp = s["n_factual_error"] + s["n_unsupported_claim"]
            mark = "  ←" if s["agent_id"] == new_agent else ""
            print(f"    {s['draft_label']} {s['agent_id']:<15}  w={s['word_count']:>4}  "
                  f"total={s['n_total_issues']}  missing={s['n_missing_info']}  pp={pp}{mark}")
        print(f"  old winner (Fix 1+2 density): {old_winner}")
        print(f"  new winner (Fix 3 absolute):  {new_agent}  [{reason}]{flip}")

    print()
    print("=" * 92)
    print("Aggregate winner distribution:\n")
    print(f"  {'agent':<22}  Fix 1+2 (density)  Fix 3 (absolute mi)")
    for agent in ("agent_qwen", "agent_llama", "agent_deepseek"):
        a = old_winners.get(agent, 0)
        b = new_winners.get(agent, 0)
        print(f"  {agent:<22}  {a:>5} / {len(files)}            {b:>5} / {len(files)}")


if __name__ == "__main__":
    main()
