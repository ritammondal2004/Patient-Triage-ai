
"""CLI for the ED simulation.
                           
    python scripts/run_simulation.py --scenario normal
    python scripts/run_simulation.py --all  
    python scripts/run_simulation.py --ablation
    python scripts/run_simulation.py --daynight
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.resources import TREATMENT_BINS, mean_treatment_minutes, service_rate_per_hour
from simulation.scenarios import (
    SCENARIOS,
    compare,
    daynight_contrast,
    reassessment_ablation,
    run_scenario,
)
  
HEADERS = ("scenario", "arr", "treated", "rho", "mean", "p90", "max", "docs%", "beds%",
           "queue", "caught")


def _row(result: dict) -> tuple:
    return (
        result.get("scenario", "?")[:22],
        result["arrivals"],
        result["treated"],
        result["offered_load_rho"],
        result["mean_wait_minutes"],
        result["p90_wait_minutes"],
        result["max_wait_minutes"],
        int(result["doctor_utilisation"] * 100),
        int(result["bed_utilisation"] * 100),
        result["max_queue_length"],
        result["caught_by_reassessment"],
    )


def print_table(results: list[dict]) -> None:
    rows = [_row(r) for r in results]
    widths = [max(len(str(HEADERS[i])), *(len(str(row[i])) for row in rows))
              for i in range(len(HEADERS))]
    line = "  ".join(str(h).ljust(w) for h, w in zip(HEADERS, widths))
    print("\n" + line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))
    print("\nrho = offered load (arrivals / service capacity); over 1.0 the queue grows "
          "without bound.\nmean/p90/max are wait-to-doctor in minutes. caught = high-risk "
          "patients the\nreassessment loop pulled out of a low-priority tier before "
          "treatment.\n")


def print_service_model() -> None:
    print("\nTreatment time model (physician contact minutes, uniform inside each band):")
    for priority in sorted(TREATMENT_BINS):
        bands = "  ".join(f"p={w:.2f} -> {low:.0f}-{high:.0f}m"
                          for w, low, high in TREATMENT_BINS[priority])
        print(f"  P{priority}  {bands}   mean {mean_treatment_minutes(priority):>5} min"
              f"   mu {service_rate_per_hour(priority)}/hr")


def print_detail(result: dict) -> None:
    params = result["scenario_params"]
    print(f"\n=== {result.get('scenario')} : {result.get('label', '')} ===")
    print(f"arrivals  lambda_mean {params['lambda_per_minute_mean']}/min  "
          f"peak {params['peak_arrivals_per_hour']}/hr  "
          f"trough {params['trough_arrivals_per_hour']}/hr  "
          f"diurnal {params['diurnal']}  night_acuity {params['night_acuity']}")
    print(f"capacity  doctors {params['doctors']}  beds {params['beds']}  "
          f"mean treatment {result['mean_treatment_minutes']} min  "
          f"rho {result['offered_load_rho']}")
    print(f"flow      arrived {result['arrivals']}  treated {result['treated']}  "
          f"still waiting {result['still_waiting']}")
    print(f"wait      mean {result['mean_wait_minutes']}  "
          f"median {result['median_wait_minutes']}  p90 {result['p90_wait_minutes']}  "
          f"max {result['max_wait_minutes']}")
    print(f"load      doctors {result['doctor_utilisation']}  "
          f"beds {result['bed_utilisation']}  peak queue {result['max_queue_length']}  "
          f"mean queue {result['mean_queue_length']}")
    print(f"loop      deteriorations {result['deteriorations']}  "
          f"reassessments {result['reassessments']}  escalations {result['escalations']}")
    print(f"risk      high-risk treated {result['high_risk_treated']}  "
          f"low-tier at intake {result['high_risk_low_priority_at_intake']}  "
          f"at treatment {result['high_risk_low_priority_at_treatment']}  "
          f"caught {result['caught_by_reassessment']}")

    if result.get("scoring_errors"):
        print(f"[warn] {result['scoring_errors']} scoring errors")
    if result.get("pool_exhausted"):
        print("[warn] patient pool exhausted before the horizon; raise the pool multiplier")
    if result.get("acuity_pool_fallbacks"):
        print(f"[warn] {result['acuity_pool_fallbacks']} arrivals fell back to the other "
              "acuity sub-pool")

    print("\n  pri  treated  mean_wait  p90_wait  target  within_target%")
    for level, stats in sorted(result["by_priority"].items()):
        print(f"  P{level}   {stats['treated']:>7}  {stats['mean_wait']:>9}  "
              f"{stats['p90_wait']:>8}  {stats['target_minutes']:>6}  "
              f"{stats['within_target_pct']:>13}")

    print("\n  daypart  treated  high_risk_share  mean_wait  p90_wait  mean_intake_priority")
    for name in ("day", "night"):
        stats = result["by_daypart"].get(name, {})
        if not stats.get("treated"):
            continue
        print(f"  {name:<7}  {stats['treated']:>7}  {stats['high_risk_share']:>15}  "
              f"{stats['mean_wait']:>9}  {stats['p90_wait']:>8}  "
              f"{stats['mean_intake_priority']:>20}")


def main() -> int:
    parser = argparse.ArgumentParser(description="PatientTriage.ai ED flow simulation")
    parser.add_argument("--scenario", default="normal", choices=sorted(SCENARIOS))
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--ablation", action="store_true", help="reassessment on vs off")
    parser.add_argument("--daynight", action="store_true", help="day vs night contrast")
    parser.add_argument("--service-model", action="store_true",
                        help="print the treatment-time bands and exit")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--base-per-hour", type=float,
                        help="override the baseline arrival rate (default 8.5)")
    parser.add_argument("--multiplier", type=float, help="override the surge multiplier")
    parser.add_argument("--doctors", type=int)
    parser.add_argument("--beds", type=int)
    parser.add_argument("--deterioration-rate", type=float)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()

    if args.service_model:
        print_service_model()
        return 0

    overrides = {"horizon_hours": args.hours, "seed": args.seed}
    for flag, key in (("base_per_hour",  "base_per_hour"), ("multiplier", "multiplier"),
                      ("doctors", "doctors"), ("beds", "beds"),
                      ("deterioration_rate", "deterioration_rate")):
        value = getattr(args, flag, None)
        if value is not None:
            overrides[key] = value

    try:
        if args.ablation:
            payload = reassessment_ablation(seed=args.seed, horizon_hours=args.hours)
            for key in ("with_reassessment", "without_reassessment"):
                payload[key]["scenario"] = key
                print_detail(payload[key])
            print(f"\ndelta: {json.dumps(payload['delta'], indent=2)}\n")
        elif args.daynight:
            payload = daynight_contrast(**overrides)
            print("\nday vs night\n" + json.dumps(payload, indent=2))
        elif args.all:
            payload = compare(**overrides)
            print_table(payload)
        else:
            payload = run_scenario(args.scenario, **overrides)
            print_detail(payload)
    except Exception as exc:
        import traceback
        print(f"[error] simulation failed: {exc}")
        traceback.print_exc()
        return 1

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(payload, indent=2, default=str))
        print(f"[ok] wrote {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())