# Purpose:  Give each position a 64-bit hash so the engine can recognize repeated positions.
#           The idea dea is to give every (piece, square) pair a random 64-bit number. A
#           position's hash is the XOR of the numbers for everything that is true about it.
#           XOR undoes itself (a ^ b ^ b == a), so when a move changes a few facts the board
#           updates the hash by XOR-ing only those facts in or out, instead of rehashing all
#           64 squares. Two different positions share a hash only with probability about 1 in
#           2**64, which the engine treats as never occur.


import random

from config import ZOBRIST_SEED

_rng = random.Random(ZOBRIST_SEED)

# Purpose: Return one random 64-bit integer from the seeded generator.
def _random_key() -> int:
    return _rng.getrandbits(64)


# PIECE_KEYS[piece + 6][square]. Pieces are signed ints from -6 to 6, so adding
# 6 maps them to list indexes 0..12. Index 6 (the empty square) is never used.
PIECE_KEYS = [[_random_key() for _ in range(64)] for _ in range(13)]

# XOR-ed in when it is Black's turn.
SIDE_KEY = _random_key()

# One key per possible castling-rights bitmask (0..15).
CASTLING_KEYS = [_random_key() for _ in range(16)]

# One key per file of the en passant target square.
EN_PASSANT_KEYS = [_random_key() for _ in range(8)]

# Purpose:  Hash a position from scratch.
#
# Args:     squares: List of 64 signed piece ints (0 = empty).
#           side: 1 if White is to move, -1 if Black is.
#           castling: Castling-rights bitmask (0..15).
#           ep_square: En passant target square index, or -1 for none.
# 
# Returns: A 64-bit integer identifying the position.
def hash_position(squares, side: int, castling: int, ep_square: int) -> int:
    key = 0
    for square, piece in enumerate(squares):
        if piece:
            key ^= PIECE_KEYS[piece + 6][square]

    if side == -1:
        key ^= SIDE_KEY

    key ^= CASTLING_KEYS[castling]

    if ep_square != -1:
        key ^= EN_PASSANT_KEYS[ep_square & 7]

    return key