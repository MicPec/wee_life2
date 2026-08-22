# Agent notes for wee-life2

## Commands

- Run the simulation: `uv run wee-life2`
- Run with custom size: `uv run wee-life2 --width 800 --height 600`
- Headless smoke test: `SDL_VIDEODRIVER=dummy timeout 10 uv run wee-life2`
- Compile check: `uv run python -m compileall src`
- Run test suite: `uv run python -m unittest discover tests`
- Headless balance test: `SDL_VIDEODRIVER=dummy uv run python -c "from wee_life2.simulation import Simulation; s=Simulation(); ..."`
- Open map editor: `uv run wee-life2 --edit-map`
- Use custom map file: `uv run wee-life2 --map-file my_map.json`
- Run a sample map: `uv run wee-life2 --map-file maps/maze.json` (also `maps/islands.json`, `maps/arena.json`, `maps/corridors.json`, `maps/quadrants.json`)
- Generic config override: `uv run wee-life2 --set KEY=VALUE` (repeatable; any `core/config.py` constant, e.g. `--set MATING_RATE=0.3 --set RADIATION_DAMAGE=0.5`), value is cast to match the existing constant's type (bool/int/float/str); errors out on an unknown key
- Generic config inspection: `uv run wee-life2 --get KEY` (repeatable; prints current value(s) and exits without launching the sim/editor)
- Load config from JSON: `uv run wee-life2 --config-file my_config.json` (flat JSON dict of all public `core/config.py` constants; loaded before `--set`, so `--set` can override values from the file)
- Open config editor: `uv run wee-life2 --edit-config` (Textual TUI for editing and saving JSON presets; `wee-life2 --config-file my_config.json --edit-config` opens that file)
- The old per-option flags (`--radioactive-damage`, `--lava-damage`, `--food-on-death-chance`, `--mating-rate`, `--asexual-cooldown-multiplier`) were removed in favor of the generic `--set`/`--get` system in `main.py` (`_apply_config_overrides`/`_print_config_values`)
- In-simulation controls: `ESC` quit, `H` toggle help, `L` toggle legend, `SPACE` pause, `LMB` spawn, `RMB` remove, `R` spawn random organisms, `E` toggle map edit mode
- In edit mode: `0-5` select tool, `LMB` draw, `RMB` erase, `S` save, `C` clear, `R` randomize, `E` exit, `ESC` quit
- Hover an organism while paused to see its DNA/stats panel
- `touch` gene now detects and steers away from walls and environmental hazards (radioactive and lava tiles); `World.is_hazard()` is the generic hook for future hazard types. It also treats water as a hazard for organisms lacking the `amphibious` gene (checked via `organism.dna.genes`, not the per-tick phenotype flag, so it works regardless of gene order)
- `memory` gene consumes `PerceptionEvent`s from `eye`/`scent`/`touch`, remembers interesting tiles, and recalls them as steering hints. If an organism has several `memory` genes, only the first one runs the logic, but their parameters are aggregated (`capacity`/`ray_count` sum, `retention`/`perception_range`/`recall_range` max, `*_weight` sum). Recall ignores memories more than ~126° behind the organism and caps the combined weight at 0.5, so memory nudges rather than dominates.
- Map editor tools: `0` empty, `1` wall, `2` radioactive, `3` lava, `4` water, `5` heal
- Water tiles (`World.TILE_WATER`, `World.is_water()`) are walkable but not a hazard: organisms without the `amphibious` gene get `config.WATER_SPEED_PENALTY` velocity and `config.WATER_DROWN_DAMAGE` energy drain per tick; `amphibious` gene organisms move at full speed and regen energy while swimming
- `eye`/`scent` genes discount (multiply steering weight by `config.WATER_SIGHT_DISCOUNT`, stacking if both apply) any food/mate target whose line of sight/smell crosses water (`World.line_crosses_water()`, skipped for `amphibious` organisms via `organism.dna.genes`, not the phenotype flag) or a radioactive/lava tile (`World.line_crosses_hazard()`, applies to all organisms)
- `eye`/`scent` only generate a food-seeking drive if the organism has a `metabolism` gene (checked via `organism.dna.genes`); without it, food is invisible to those senses (mate/threat detection unaffected)
- `herd` gene: attracts organisms toward others sharing the same `organism.name` (species label); `amphibious` gene: safe/full-speed water movement
- `venom` gene: when a carrier's `jaw` bites another organism, a damage-over-time effect is applied to the victim (stored in `organism.venom_stacks`); damage per tick = `toxicity` × (1 − victim's `toxin_resistance`); `venom` also grants partial toxin resistance to the carrier; `toxin_gland` only poisons remains on death, `venom` actively poisons live prey
- `jaw` refuses to target organisms sharing the same `organism.name` (species label) as prey by default; the `cannibal` gene (checked via `organism.dna.genes`) lifts this restriction and adds extra aggression scaled by hunger
- `cannibal` also exploits kin's `pheromone` mating signal (`other.pheromone_strength`) to hunt weaker same-species kin from long range (`hunt_range`, default 160), well beyond `jaw`'s bite reach — the same broadcast meant to attract mates instead attracts a predator
- `fear` sets `organism.alarm_level` (0-1) whenever it directly spots a threat; other `fear`-carrying kin (same `organism.name`) within `alarm_range` (default 130) sense that alarm secondhand and flee the alarmed kin's position too, even without seeing the threat themselves — panic ripples through a herd faster than individual perception
- `asexual` gene: on a per-instance cooldown timer, if the carrier is of mating age (`Organism.is_of_mating_age()`) and has spare energy, it clones its own DNA (`DNA.clone()`, no crossover), mutates it at a boosted rate (`config.MUTATION_RATE * mutation_multiplier`), and spawns the child directly via `World.add_organism()` — no partner needed. Before spawning it checks `World.local_density()` against the same `config.MATING_DENSITY_RADIUS`/`MATING_DENSITY_LIMIT` used by sexual mating (fixed bug: it used to bypass this crowd-control check entirely, letting a single dominant `asexual` genotype cause runaway population avalanches); if blocked, the cooldown timer is left untouched so it retries every subsequent tick until the area thins out
- `World.local_density(pos, radius, exclude=())` is the shared helper for counting nearby living organisms, used by both `World._try_mating()` and `AsexualGene.apply()`
- Genome length (via `DNA.mutate()`'s unbounded insertion/deletion random walk) and per-gene `count`/`size` params (via `Gene.mutate()`, which only floors at 0.0, no upper bound) can grow indefinitely over generations, producing huge/long chain-like organisms; `Organism._build_body()` caps this by uniformly scaling down all body part offsets/sizes so the organism's `radius` never exceeds `config.MAX_ORGANISM_RADIUS`
- On Wayland sessions, `main.py` defaults `SDL_VIDEODRIVER=wayland` (unless already set) to avoid an SDL/XWayland GLX probe crash (`BadValue ... X_GLXCreateContext`) seen with some NVIDIA/EGL driver setups

## Performance

- The most expensive simulation paths are: scent/eye scans, wall-circle collision checks, and spatial-grid queries.
- Key optimizations applied:
  - Tile map line-of-sight/hazard checks use an inline Bresenham walk instead of a generator.
  - `Touch` uses a single combined ray cast against the tile grid instead of world-unit sampling.
  - `Scent` and `Eye` compute squared distances first and only run line-of-sight checks for targets that can beat the current best score.
  - `Organism` caches nearby organisms per tick and stores immutable genome-derived counts.
  - `Renderer` caches a fully static map background (animated tiles are excluded via `draw_tiles(skip_tiles=...)`) and only redraws pulsing tiles (`ANIMATED_TILES` in `render/tile_drawing.py`) each frame, using rectangles pre-merged horizontally and vertically in `Renderer._rebuild_animated_tile_rects` (tile layout is static between cache rebuilds). The map blit covers the whole screen, so `render()` skips the redundant screen-wide background fill.
  - Body parts are sorted once in `Organism._build_body` instead of every frame.
- Repeatable performance smoke test:
  - `uv run python -m unittest tests.test_performance`
- Verification commands:
  - `uv run python -m compileall src`
  - `uv run python -m unittest discover tests`
  - `SDL_VIDEODRIVER=dummy timeout 10 uv run wee-life2`
  - `SDL_VIDEODRIVER=dummy timeout 5 uv run wee-life2 --edit-map`
  - Textual editor headless tests are in `tests/test_config_editor.py`; the editor can also be opened manually with `uv run wee-life2 --edit-config`

## Architecture

- Uses `uv` for dependency management and virtual environment.
- Entry point: `wee_life2/main.py`.
- External dependencies: Pygame (simulation/editor rendering), Textual (config editor TUI), textual-slider (sliders in the config editor).
- Genes are registered in `wee_life2/genes/__init__.py:GENE_REGISTRY`.
- Body parts are assembled from `BodyPartBlueprint` objects returned by each gene.
- Simulation loop is in `wee_life2/simulation.py`.
