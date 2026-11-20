"""Headless batch of seeded simulation runs with per-gene carrier tracking.

Usage: uv run python scripts/batch_runs.py OUT_DIR [--seeds 30] [--ticks 50000] [--every 1000] [--jobs N]

OUT_DIR gets: genes_seed_XX.jsonl (one row per sample), final.csv (last row
per seed), summary.json (cross-seed stats at the final tick), meta.json, and
runs/seed_XX/ with the full RunLogger output of every seed. A seed that
crashes is logged and listed under "failed_seeds" instead of aborting the batch.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import subprocess
import sys
import time
import traceback
from multiprocessing import Pool
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"


def sample(world, tick: int, gene_kinds: list[str]) -> dict:
    alive = [o for o in world.organisms if not o.is_dead]
    n = len(alive)
    row = {
        "tick": tick,
        "population": n,
        "food": len(world.food),
        "species": len({o.name for o in alive}),
        "max_generation": max((o.generation for o in alive), default=0),
        "mean_genes": round(sum(len(o.dna.genes) for o in alive) / n, 3) if n else 0.0,
    }
    for kind in gene_kinds:
        carriers = sum(1 for o in alive if any(g.kind == kind for g in o.dna.genes))
        row[f"carrier_{kind}"] = round(carriers / n, 4) if n else 0.0
    glows = [g.params["glow"] for o in alive for g in o.dna.genes if g.kind == "color"]
    sizes = [g.params["size"] for o in alive for g in o.dna.genes if g.kind == "color"]
    row["mean_color_glow"] = round(statistics.fmean(glows), 4) if glows else None
    row["mean_color_size"] = round(statistics.fmean(sizes), 4) if sizes else None
    return row


def run_seed(args: tuple[int, int, int, str]) -> dict | None:
    try:
        return _run_seed(*args)
    except Exception:
        print(f"seed {args[0]} FAILED:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        return None


def _run_seed(seed: int, ticks: int, every: int, out_dir: str) -> dict:
    from wee_life2.core import config

    config.STATS_BASE_DIR = str(Path(out_dir) / "runs" / f"seed_{seed:02d}")
    random.seed(seed)
    from wee_life2.genes import GENE_REGISTRY
    from wee_life2.simulation import Simulation

    kinds = sorted(GENE_REGISTRY)
    sim = Simulation()
    started = time.time()
    with open(Path(out_dir) / f"genes_seed_{seed:02d}.jsonl", "w") as f:
        row = sample(sim.world, 0, kinds)
        f.write(json.dumps(row) + "\n")
        for tick in range(1, ticks + 1):
            sim.step()
            if tick % every == 0:
                row = sample(sim.world, tick, kinds)
                f.write(json.dumps(row) + "\n")
                f.flush()
    sim.stats.close()
    row.update(seed=seed, run_dir=str(sim.stats.run_dir), seconds=round(time.time() - started, 1))
    print(f"seed {seed} done: pop {row['population']} in {row['seconds']} s", flush=True)
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--ticks", type=int, default=50000)
    parser.add_argument("--every", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = parser.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=False)

    from wee_life2.core import config

    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "src"], capture_output=True, text=True).stdout.strip())
    public = {k: getattr(config, k) for k in dir(config) if k.isupper()}
    meta = {"commit": commit, "src_dirty": dirty, "seeds": list(range(a.seeds)), "ticks": a.ticks,
            "sample_every": a.every, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "python": sys.version,
            "config": public}
    (out / "meta.json").write_text(json.dumps(meta, indent=2, default=str))

    with Pool(a.jobs) as pool:
        results = pool.map(run_seed, [(s, a.ticks, a.every, str(out)) for s in range(a.seeds)], chunksize=1)
    failed = [s for s, r in enumerate(results) if r is None]
    finals = [r for r in results if r is not None]
    if not finals:
        sys.exit(f"all seeds failed: {failed}")

    with open(out / "final.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(finals[0]))
        writer.writeheader()
        writer.writerows(finals)

    alive = [r for r in finals if r["population"] > 0]
    stats = {}
    for key in finals[0]:
        if key in ("seed", "run_dir", "tick"):
            continue
        values = [r[key] for r in alive if isinstance(r[key], (int, float))]
        if values:
            stats[key] = {"mean": round(statistics.fmean(values), 4),
                          "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
                          "min": min(values), "max": max(values), "n": len(values)}
    summary = {"seeds": a.seeds, "ticks": a.ticks, "surviving_seeds": len(alive),
               "extinct_seeds": [r["seed"] for r in finals if r["population"] == 0], "failed_seeds": failed,
               "note": "stats over surviving seeds at the final tick; carrier_X = share of living organisms with >=1 X gene",
               "final_tick": stats}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    meta["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    print(json.dumps({k: v["mean"] for k, v in stats.items() if k.startswith("carrier_")}, indent=1))


if __name__ == "__main__":
    main()
