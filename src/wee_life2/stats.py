"""Per-run statistics logging for the wee-life2 simulation.

Each run creates a timestamped directory under ``config.STATS_BASE_DIR`` and
writes compact, append-only files:

* ``timeseries.csv`` — population-level metrics sampled every
  ``config.STATS_SAMPLE_INTERVAL`` ticks.
* ``events.jsonl`` — births, deaths, speciations and extinctions per species.
* ``census.jsonl`` — per-species composition snapshots every
  ``config.STATS_CENSUS_INTERVAL`` ticks.
* ``organisms.jsonl`` — one record per organism created during the run,
  containing its initial state and full genome for visualization.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .core import config

if TYPE_CHECKING:
    from .core.organism import Organism
    from .core.world import World


class RunLogger:
    """Logs time-series, events and census snapshots for one simulation run.

    The logger is intentionally simple and append-only: files are kept open for
    writing and flushed at sample boundaries so that a crash still leaves a
    usable partial run on disk.
    """

    def __init__(self, world: World, enabled: bool | None = None) -> None:
        self.enabled = config.STATS_ENABLED if enabled is None else enabled
        self.sample_interval = config.STATS_SAMPLE_INTERVAL
        self.census_interval = config.STATS_CENSUS_INTERVAL

        self._tick = 0.0
        self._last_sample_tick = 0.0
        self._last_census_tick = 0.0

        self._prev_births = 0
        self._prev_total_deaths = 0
        self._prev_births_by_species: dict[str, int] = {}
        self._prev_deaths_by_species: dict[str, int] = {}
        self._prev_species_counts: dict[str, int] = {}
        self._seen_species: set[str] = set()

        self._timeseries_file = None
        self._timeseries_writer = None
        self._events_file = None
        self._census_file = None
        self._organisms_file = None
        self._run_dir: Path | None = None

        if not self.enabled:
            return

        self._run_dir = self._make_run_dir()
        self._run_dir.mkdir(parents=True, exist_ok=True)

        self._timeseries_path = self._run_dir / "timeseries.csv"
        self._events_path = self._run_dir / "events.jsonl"
        self._census_path = self._run_dir / "census.jsonl"
        self._organisms_path = self._run_dir / "organisms.jsonl"

        self._timeseries_file = open(self._timeseries_path, "w", newline="", encoding="utf-8")
        self._timeseries_writer = csv.DictWriter(
            self._timeseries_file,
            fieldnames=[
                "tick",
                "organisms",
                "food",
                "births",
                "deaths",
                "species_count",
                "diversity",
                "avg_energy",
                "avg_age",
                "top_5",
            ],
        )
        self._timeseries_writer.writeheader()

        self._events_file = open(self._events_path, "w", encoding="utf-8")
        self._census_file = open(self._census_path, "w", encoding="utf-8")
        self._organisms_file = open(self._organisms_path, "w", encoding="utf-8")

        # Record run start metadata so the analysis tool knows the configuration.
        meta = {
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "world_width": world.width,
            "world_height": world.height,
            "max_organisms": world.max_organisms,
            "sample_interval": self.sample_interval,
            "census_interval": self.census_interval,
        }
        with open(self._run_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            f.write("\n")

        # Save a snapshot of the map so the analysis tool can correlate
        # population dynamics with the tile layout.
        with open(self._run_dir / "map.json", "w", encoding="utf-8") as f:
            json.dump(world.save_tiles(), f)
            f.write("\n")

    @property
    def run_dir(self) -> Path | None:
        """Return the output directory for this run, or ``None`` if logging is disabled."""
        return self._run_dir

    def _make_run_dir(self) -> Path:
        """Create a unique, timestamped directory name under the configured base."""
        base = Path(config.STATS_BASE_DIR)
        if not base.is_absolute():
            base = Path.cwd() / base

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Add a tiny random suffix to avoid collisions if two runs start in the same second.
        suffix = f"{datetime.now().microsecond:04x}"
        return base / f"{timestamp}_{suffix}"

    def step(self, world: World, dt: float) -> None:
        """Advance the internal tick counter from the world and sample when a boundary is crossed.

        ``world.tick`` is the canonical generation counter; it is converted from
        wall-clock dt using ``config.FPS`` so one rendered frame at 60 FPS
        increments the counter by one tick.
        """
        if not self.enabled:
            return

        self._tick = world.tick

        if self._tick - self._last_sample_tick >= self.sample_interval:
            self._sample(world)
            self._last_sample_tick = self._tick

        if self._tick - self._last_census_tick >= self.census_interval:
            self._census(world)
            self._last_census_tick = self._tick

    def _sample(self, world: World) -> None:
        """Write one population-level row and any per-species events."""
        organisms = [o for o in world.organisms if not o.is_dead]
        food = len(world.food)

        counts: dict[str, int] = {}
        total_energy = 0.0
        total_age = 0.0
        for o in organisms:
            counts[o.name] = counts.get(o.name, 0) + 1
            total_energy += o.energy
            total_age += o.age

        total = len(organisms)
        species_count = len(counts)
        avg_energy = total_energy / total if total else 0.0
        avg_age = total_age / total if total else 0.0

        # Shannon diversity (natural log).
        diversity = 0.0
        if total:
            for c in counts.values():
                p = c / total
                if p > 0:
                    diversity -= p * math.log(p)

        top_5 = sorted(counts.items(), key=lambda x: -x[1])[:5]

        self._timeseries_writer.writerow(
            {
                "tick": round(self._tick),
                "organisms": total,
                "food": food,
                "births": world.births,
                "deaths": sum(world.deaths.values()),
                "species_count": species_count,
                "diversity": round(diversity, 4),
                "avg_energy": round(avg_energy, 2),
                "avg_age": round(avg_age, 2),
                "top_5": json.dumps(top_5, ensure_ascii=False),
            }
        )
        self._timeseries_file.flush()

        # Per-species events: births and deaths since the previous sample.
        births_by_species = world.births_by_species
        deaths_by_species = world.deaths_by_species
        total_deaths = sum(world.deaths.values())

        species_set = set(counts) | set(births_by_species) | set(deaths_by_species)
        for name in species_set:
            births = births_by_species.get(name, 0) - self._prev_births_by_species.get(name, 0)
            deaths = deaths_by_species.get(name, 0) - self._prev_deaths_by_species.get(name, 0)
            if births > 0 or deaths > 0:
                event = {
                    "tick": round(self._tick),
                    "event": "species_update",
                    "species": name,
                    "births": births,
                    "deaths": deaths,
                    "count": counts.get(name, 0),
                }
                self._events_file.write(json.dumps(event, ensure_ascii=False) + "\n")

            if name not in self._seen_species and counts.get(name, 0) > 0:
                self._seen_species.add(name)
                self._events_file.write(
                    json.dumps(
                        {
                            "tick": round(self._tick),
                            "event": "speciation",
                            "species": name,
                            "count": counts[name],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

            # Detect extinctions only for species we have already seen.
            if name in self._seen_species and self._prev_species_counts.get(name, 0) > 0 and counts.get(name, 0) == 0:
                self._events_file.write(
                    json.dumps(
                        {
                            "tick": round(self._tick),
                            "event": "extinction",
                            "species": name,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        if world.births - self._prev_births > 0 or total_deaths - self._prev_total_deaths > 0:
            self._events_file.write(
                json.dumps(
                    {
                        "tick": round(self._tick),
                        "event": "totals",
                        "births": world.births - self._prev_births,
                        "deaths": total_deaths - self._prev_total_deaths,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        self._prev_births = world.births
        self._prev_total_deaths = total_deaths
        self._prev_births_by_species = dict(births_by_species)
        self._prev_deaths_by_species = dict(deaths_by_species)
        self._prev_species_counts = dict(counts)
        self._events_file.flush()

    def _census(self, world: World) -> None:
        """Write one per-species snapshot."""
        organisms = [o for o in world.organisms if not o.is_dead]
        counts: dict[str, int] = {}
        energy_by_species: dict[str, float] = {}
        age_by_species: dict[str, float] = {}
        for o in organisms:
            name = o.name
            counts[name] = counts.get(name, 0) + 1
            energy_by_species[name] = energy_by_species.get(name, 0.0) + o.energy
            age_by_species[name] = age_by_species.get(name, 0.0) + o.age

        total = len(organisms)
        if not total:
            return

        tick = round(self._tick)
        for name, count in sorted(counts.items(), key=lambda x: -x[1]):
            record = {
                "tick": tick,
                "species": name,
                "count": count,
                "pct": round(count / total, 4),
                "avg_energy": round(energy_by_species[name] / count, 2),
                "avg_age": round(age_by_species[name] / count, 2),
            }
            self._census_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._census_file.flush()

    def log_organism(self, organism: Organism) -> None:
        """Write one record when a new organism is created.

        This is intentionally decoupled from tick/census sampling; the
        analysis tool can reconstruct the creature's look from ``dna`` and
        place it using the initial position and angle.
        """
        if not self.enabled or self._organisms_file is None:
            return
        record = {
            "uid": getattr(organism, "_uid", None),
            "name": organism.name,
            "x": round(organism.position[0], 2),
            "y": round(organism.position[1], 2),
            "angle": round(organism.angle, 4),
            "radius": round(organism.radius, 2),
            "dna": organism.dna.to_dict(),
        }
        self._organisms_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._organisms_file.flush()

    def log_reset(self, world: World) -> None:
        """Record a reset event and reset internal state to match the new population."""
        if not self.enabled:
            return

        self._tick = world.tick
        self._last_sample_tick = self._tick
        self._last_census_tick = self._tick

        self._events_file.write(
            json.dumps(
                {
                    "tick": round(self._tick),
                    "event": "simulation_reset",
                    "organisms": len(world.organisms),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        self._events_file.flush()
        self._prev_total_deaths = sum(world.deaths.values())
        self._prev_births_by_species = dict(world.births_by_species)
        self._prev_deaths_by_species = dict(world.deaths_by_species)
        self._prev_species_counts = {}
        self._seen_species.clear()

    def close(self) -> None:
        """Flush and close all open log files."""
        if not self.enabled:
            return

        if self._timeseries_file is not None:
            self._timeseries_file.flush()
            self._timeseries_file.close()
            self._timeseries_file = None
            self._timeseries_writer = None

        if self._events_file is not None:
            self._events_file.flush()
            self._events_file.close()
            self._events_file = None

        if self._census_file is not None:
            self._census_file.flush()
            self._census_file.close()
            self._census_file = None

        if self._organisms_file is not None:
            self._organisms_file.flush()
            self._organisms_file.close()
            self._organisms_file = None
