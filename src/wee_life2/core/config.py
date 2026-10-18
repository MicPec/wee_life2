"""Global configuration and constants for the wee-life2 simulation."""

# Window / rendering
WINDOW_WIDTH = 1200  # simulation window width in pixels
WINDOW_HEIGHT = 900  # simulation window height in pixels
FPS = 60  # target frames per second (rendering only)
GRAY_WITH_AGE = True  # whether organisms fade to gray as they age
TILE_SIZE = 20  # size of one world tile in pixels

# Simulation time base
# Every per-tick rate in the codebase (energy drain, ageing, movement, gene
# timers) is expressed per *tick*, and wall-clock dt is converted with
# `dt * config.TICKS_PER_SECOND`. Keep this separate from FPS: FPS is only the
# rendering target, so changing it must not silently rescale the whole ecology.
TICKS_PER_SECOND = 60.0  # simulation ticks per second of wall-clock time

# World
WORLD_WIDTH = 1200  # logical world width in pixels
WORLD_HEIGHT = 900  # logical world height in pixels
POPULATION_CAP = 0.1  # soft fraction of world area that can be covered by organisms
SPECIES_CAP_FRACTION = 1.0  # no single species can exceed this fraction of max_organisms

# Statistics logging
STATS_ENABLED = True  # write per-run statistics to disk
STATS_BASE_DIR = "data/runs"  # run output directories are created under this path
STATS_SAMPLE_INTERVAL = 60  # ticks between time-series samples
STATS_CENSUS_INTERVAL = 300  # ticks between per-species census snapshots

# Physics / organism
MAX_SPEED = 2.0  # maximum base movement speed
FRICTION = 0.92  # velocity decay applied each tick
TURN_RATE = 0.30  # how fast an organism can change its heading
MAX_ORGANISM_RADIUS = 20.0  # hard cap on body radius; oversized genomes are scaled down to fit

# Age-based movement slowdown
AGE_SLOWDOWN_START = 0.80  # fraction of lifespan at which movement begins to slow
AGE_SLOWDOWN_END_SPEED = 0.2  # movement speed multiplier at the end of lifespan

# Energy
BASE_ENERGY = 160.0  # starting and maximum energy of a new organism
ENERGY_GAIN_FROM_FOOD = 45.0  # energy restored by eating a food item
ENERGY_COST_MOVE = 0.03  # base energy cost per tick while moving
ENERGY_COST_STAY = 0.008  # base energy cost per tick while idle
ENERGY_COST_ATTACK = 0.15  # energy the attacker spends per bite (per tick while biting)
ENERGY_COST_MATE = 20.0  # energy spent by each parent during sexual reproduction
ENERGY_TO_MATE = 35.0  # minimum energy required to be eligible for mating
REFERENCE_BODY_MASS = 200.0  # body mass (sum of body part areas) treated as mass ratio 1.0
MASS_UPKEEP_FACTOR = 1.0  # how strongly body mass scales idle upkeep (up when heavy, down when light; floored at 0)
GENE_UPKEEP_COST = 0.005  # extra idle energy cost per tick for each gene in the genome

# Lifespan / reproduction
MAX_GENES = 16  # hard cap on genome length; insertions are ignored once reached
LIFESPAN_BASE = 6000  # base lifespan in ticks
MATURITY_MIN_FRACTION = 0.15  # too young to mate below this fraction of lifespan
BABY_SIZE_FRACTION = 0.4  # visual scale of newborn organisms at age 0
ASEXUAL_MATURITY_MIN_FRACTION = 0.4  # asexual reproduction needs twice the maturity time
MATURITY_MAX_FRACTION = 0.8  # too old to mate above this fraction of lifespan
MUTATION_RATE = 0.1  # chance per gene that a parameter mutates during reproduction
MUTATION_STRENGTH = 0.15  # how much a mutated parameter can change
MUTATION_STEP_FLOOR = 0.05  # minimum additive mutation scale; lets 0.0-valued parameters evolve
MUTATION_INSERTION_RATE = 0.05  # probability of adding a new gene during structural mutation
CROSSOVER_BLEND_RATE = 0.5  # chance that a shared gene's parameters are averaged instead of copied
MATING_RATE = 0.3  # probability that a collision between two eligible organisms results in mating
MATING_DIVERSITY = 0.45  # maximum genome diversity allowed for two organisms to mate
MATING_DENSITY_RADIUS = 80  # radius for checking local population density before mating
MATING_DENSITY_LIMIT = 3  # maximum number of nearby organisms allowed for mating
MATING_DEATH_CHANCE = 0.05  # chance that mating fails and one parent dies instead
ASEXUAL_COOLDOWN_RATE = 2.0  # global scale on the asexual gene's reproduction cooldown; lower = more frequent

# Random spawn weighting for initial genomes
GENE_DEFAULT_SPAWN_WEIGHT = 1.0  # default relative chance of any gene in random genomes
GENE_SPAWN_WEIGHTS = {  # per-gene overrides; higher = more common
    "asexual": 0.4,  # much rarer, because it tends to dominate the map
    "spike": 0.7,  # rarer, since it directly raises aggression
    "cannibal": 0.6,  # rarer, since it amplifies aggression when starving
    "pheromone": 1.5,  # boosts mate signalling
    "eye": 1.5,  # sight is a strong sense
    "scent": 1.8,  # scent is a strong sense
    "leg": 1.3,  # needed for movement
    "memory": 1.2,  # long-term navigation; benefits from paired senses
    "jaw": 1.8,  # needed to eat
    "touch": 1.7,  # needed to avoid hazards
    "metabolism": 1.8,  # needed for energy and longevity
}

# Hazards
RADIATION_DAMAGE = 3.0  # energy damage per tick on radioactive tiles
LAVA_DAMAGE = 10.0  # energy damage per tick on lava tiles

# Healing
HEAL_ENERGY = 0.3  # energy restored per tick while standing on a heal tile

# Ambient food stream
FOOD_SPAWN_CHANCE = 0.8  # probability of spawning one food item per second
FOOD_MAX_ITEMS = 80  # ambient spawning pauses while this many food items exist

# Death / remains
FOOD_ON_DEATH_CHANCE = 0.75  # probability a dead organism leaves behind edible remains

# Water
WATER_SPEED_PENALTY = 0.25  # velocity multiplier for non-amphibious organisms in water
WATER_DROWN_DAMAGE = 0.3  # energy drained per tick while non-amphibious organisms are in water
AMPHIBIOUS_LAND_DRAIN = 0.1  # energy drained per tick while amphibious organisms are on land
WATER_SIGHT_DISCOUNT = 0.25  # eye/scent score multiplier for targets seen/smelled across water (non-amphibious)

# Map generation
MAP_WATER_FRACTION_MIN = 0.35  # lowest share of the board's interior flooded into lakes by the map generator (R)
MAP_WATER_FRACTION_MAX = 0.40  # highest share of the interior flooded; each map draws a value in [MIN, MAX]
MAP_WALL_FRACTION = 0.05  # share of the interior drawn as long one-tile-thick wall lines and corridors
MAP_HAZARD_FRACTION = 0.03  # share of the interior covered by small radioactive/lava patches
MAP_HEAL_FRACTION = 0.006  # share of the interior covered by small heal oases
MAP_NOISE_SCALE = 14.0  # terrain feature size in tiles; larger = bigger lakes and islands
MAP_NOISE_OCTAVES = 4  # fractal noise layers; more = more ragged coastlines

# Tiles
TILE_EMPTY = 0  # walkable empty tile
TILE_WALL = 1  # impassable wall
TILE_RADIOACTIVE = 2  # hazard tile that deals radiation damage
TILE_LAVA = 3  # hazard tile that deals heavy fire damage
TILE_WATER = 4  # shallow water tile; slow/damaging for non-amphibious organisms
TILE_HEAL = 5  # regenerative tile that slowly restores energy

# Colors
COLOR_BACKGROUND = (20, 20, 30)  # window background
COLOR_WALL = (80, 80, 90)  # wall tiles
COLOR_RADIOACTIVE = (160, 10, 160)  # radioactive hazard tiles (violet)
COLOR_LAVA = (220, 60, 30)  # lava hazard tiles
COLOR_WATER = (40, 100, 190)  # water tiles
COLOR_HEAL = (80, 200, 80)  # regenerative heal tiles (green)
COLOR_FOOD = (120, 200, 80)  # edible food remains
COLOR_POISON = (200, 60, 80)  # poisonous remains left by toxin_gland
