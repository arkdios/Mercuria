# Purpose: Cache search results so the engine does not repeatedly solve the same position

from typing import Optional

from config import MATE_THRESHOLD

EXACT = 0 #  the score is the true value.
LOWER = 1 # the true value is at least this score (the search failed high).
UPPER = 2 # the true value is at most this score (the search failed low).

# Purpsoe: Convert a search score to the form stored in the table.
def score_to_table(score: int, ply: int) -> int:
    if score >= MATE_THRESHOLD:
        return score + ply
    
    if score <= -MATE_THRESHOLD:
        return score - ply
    return score

# Purpose: Convert a stored score back to a root-relative search score.
def score_from_table(score: int, ply: int) -> int:
    if score >= MATE_THRESHOLD:
        return score - ply
    
    if score <= -MATE_THRESHOLD:
        return score + ply
    return score

# Purpose: A size-capped cache of search results, keyed by position hash.
class TranspositionTable:

    # Purpose: Create an empty table that holds at most max_entries positions.
    def __init__(self, max_entries: int) -> None:
        self._entries = {}
        self._max_entries = max_entries

    # Purpose: Look up a position.
    # Returns: (depth, flag, score, best_move) if the position is stored,
    #          otherwise None. The score is in table form.
    def probe(self, key: int) -> Optional[tuple]:
        return self._entries.get(key)

    # Purpose: Save a result, keeping the deeper one if the position is already stored.
    def store(self, key: int, depth: int, flag: int, score: int, best_move: int) -> None:
        existing = self._entries.get(key)

        if existing is not None and existing[0] > depth:
            return
        
        if existing is None and len(self._entries) >= self._max_entries:
            self._entries.clear()

        self._entries[key] = (depth, flag, score, best_move)

    # Purpose: Return the number of stored positions.
    def __len__(self) -> int:
        return len(self._entries)