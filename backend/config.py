# Purpose:  Keeps the tunable settings in one place
#           Tunable settings for the Mercuria backend.
#           Import what you need with ``from config import NAME``

import os

#   Search
#   Score for "the side to move is checkmated".
MATE_SCORE = 100_000

#   Deepest line (in half-moves) the search may follow, including check
#   extensions. It also sizes the killer-move table.
MAX_PLY = 128

#   Any score at or beyond this is a forced mate rather than a material score.
MATE_THRESHOLD = MATE_SCORE - MAX_PLY

#   Larger than any real score. Used as the initial alpha-beta window.
INFINITY = MATE_SCORE + 1_000

#   Highest depth iterative deepening will try if time never runs out.
MAX_DEPTH = 64

#   The search checks the clock once per this many nodes. Must be a power of two
#   because the check uses a bit mask.
NODE_CHECK_INTERVAL = 1024

#   Thinking time in milliseconds: default, and the allowed range for requests.
DEFAULT_THINK_MS = 4000 # = 4 seconds
MIN_THINK_MS = 100 # 0.1 seconds
MAX_THINK_MS = 10_000  # also the largest value the website's thinking-time box accepts aka. 10 seconds

#   Maximum positions kept in the transposition table. Each entry costs roughly
#   200 bytes in Python, so 200_000 entries is about 40 MB.
TT_MAX_ENTRIES = 200_000

#   Evaluation
#   When the combined value of both sides' knights, bishops, rooks and queens
#   falls to this level or below, the game counts as an endgame and the king is
#   scored for activity instead of safety. The full starting set is 6400.
ENDGAME_MATERIAL_LIMIT = 2600

#   Hashing
#   Fixed seed so the Zobrist keys are identical on every run. This makes
#   failures reproducible. (The value spells "Merc" in ASCII.)
ZOBRIST_SEED = 0x4D657263

#   API
#   Browser origins allowed to call the API.
ALLOWED_ORIGINS = frozenset(
    origin.strip()
    for origin in os.environ.get(
        "MERCURIA_ALLOWED_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,https://arkdios.github.io/Mercuria/",
    ).split(",")
    if origin.strip()
)

#   Longest game (in half-moves) a single request may describe. Caps the work
#   the server does replaying a move list that came from the network.
MAX_MOVES_PER_REQUEST = 600