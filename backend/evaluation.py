# Purpose:  Estimate how good a position is for the side to move aka. heuristics evaluation function.
#           search.py calls evaluate(board) at the end of every line it follows and uses the
#           number to compare positions, so this has to be both sensible and FAST (it runs
#           once per search node, and Python is slow).
from board import BISHOP, BLACK, EMPTY, KING, KNIGHT, PAWN, QUEEN, ROOK, WHITE
from config import ENDGAME_MATERIAL_LIMIT


# ---------------------------------------------------------------------------
# Tunable values (centipawns)
# ---------------------------------------------------------------------------

# Value of each piece type, indexed by type (PAWN=1 ... KING=6). The king has no material
# value because it can never be captured. With these numbers one side's knights, bishops,
# rooks and queens add up to 3200, so both sides together make the 6400 that the comment
# in config.py gives for the full starting set.
PIECE_VALUES = (0, 100, 320, 330, 500, 900, 0)

# Bonus for owning both bishops.
BISHOP_PAIR_BONUS = 30

# Penalty per extra pawn stacked on one file (two pawns on a file = one penalty).
DOUBLED_PAWN_PENALTY = 10

# Penalty per pawn with no friendly pawn on either neighbouring file.
ISOLATED_PAWN_PENALTY = 15

# Bonus for a passed pawn (no enemy pawn ahead of it on its own or a neighbouring file),
# indexed by how far it has advanced from its own side: 0 = its starting row, 7 = last row.
PASSED_PAWN_BONUS = (0, 5, 10, 20, 35, 60, 100, 0)

# Bonus for a rook on a file with no pawns at all (open), or with no friendly pawns (semi-open).
ROOK_OPEN_FILE_BONUS = 15
ROOK_SEMI_OPEN_FILE_BONUS = 8

# Small bonus for the side to move. It keeps the score from flip-flopping between
# even and odd search depths.
TEMPO_BONUS = 10


# ---------------------------------------------------------------------------
# Piece-square tables
# ---------------------------------------------------------------------------
# Each table has 64 entries, written the way the board looks from White's side: the top
# row is rank 8 and the bottom row is rank 1, a-file on the left. That is the same order
# as board.py's squares, so a White piece on square sq uses table[sq]. For a Black piece
# the table is flipped upside down (index sq ^ 56 swaps rank 1 with rank 8, and so on),
# so both sides are scored the same way from their own point of view.

_PAWN_TABLE = (
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  50,  50,  50,  50,  50,
     10,  10,  20,  30,  30,  20,  10,  10,
      5,   5,  10,  25,  25,  10,   5,   5,
      0,   0,   0,  20,  20,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -20, -20,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
)

_KNIGHT_TABLE = (
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
)

_BISHOP_TABLE = (
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
)

_ROOK_TABLE = (
      0,   0,   0,   0,   0,   0,   0,   0,
      5,  10,  10,  10,  10,  10,  10,   5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
      0,   0,   0,   5,   5,   0,   0,   0,
)

_QUEEN_TABLE = (
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
     -5,   0,   5,   5,   5,   5,   0,  -5,
    -10,   0,   5,   5,   5,   5,   0, -10,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
)

# King while there are many pieces on the board: stay home behind the pawns (corners
# near the castled squares are best, the open centre is dangerous).
_KING_MIDDLEGAME_TABLE = (
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
)

# King in an endgame: with little material left it is safe, and a centralised king is a
# strong piece, so reward the centre and punish the edges.
_KING_ENDGAME_TABLE = (
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
)

# Material and position combined, built once when this file is first imported so that
# scoring a piece during search is a single list lookup.
#   _PIECE_TABLE[piece + 6][sq] = score of that signed piece on that square, from
#   White's point of view (Black pieces come out negative). Kings are left at 0 here
#   because their table depends on the game phase (see evaluate).
_PIECE_TABLE = [[0] * 64 for _ in range(13)]
for _kind, _table in ((PAWN, _PAWN_TABLE), (KNIGHT, _KNIGHT_TABLE), (BISHOP, _BISHOP_TABLE),
                      (ROOK, _ROOK_TABLE), (QUEEN, _QUEEN_TABLE)):
    for _sq in range(64):
        # White piece: its own material plus the table value for its square.
        _PIECE_TABLE[_kind + 6][_sq] = PIECE_VALUES[_kind] + _table[_sq]
        # Black piece: the same, but flipped to Black's side of the board and negated.
        _PIECE_TABLE[6 - _kind][_sq] = -(PIECE_VALUES[_kind] + _table[_sq ^ 56])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Purpose:  Score one side's pawn structure: doubled pawns, isolated pawns and passed pawns.
# Args:     own: list of 8 lists, one per file; each holds the board ROW (0 = rank 8 ... 7 =
#                rank 1) of every pawn that side has on that file.
#           enemy: the same, for the opponent.
#           is_white: True for White. White pawns move toward row 0, Black toward row 7, so
#                "ahead of the pawn" means lower rows for White and higher rows for Black.
# Returns:  The side's pawn-structure score from ITS OWN point of view (positive = good).
def _pawn_structure(own, enemy, is_white):
    score = 0
    for file in range(8):
        pawns = own[file]
        if not pawns:
            continue

        # Doubled: every pawn beyond the first on a file is a weakness.
        if len(pawns) > 1:
            score -= DOUBLED_PAWN_PENALTY * (len(pawns) - 1)

        # Isolated: no friendly pawn on the file to the left or right to support these.
        has_neighbour = (file > 0 and own[file - 1]) or (file < 7 and own[file + 1])
        if not has_neighbour:
            score -= ISOLATED_PAWN_PENALTY * len(pawns)

        # Passed: no enemy pawn ahead of it on its own file or a neighbouring file.
        # An enemy pawn BESIDE or BEHIND it cannot stop it, so only pawns ahead count.
        first = max(file - 1, 0)
        last = min(file + 1, 7)
        for row in pawns:
            blocked = False
            for f in range(first, last + 1):
                theirs = enemy[f]
                if theirs and ((min(theirs) < row) if is_white else (max(theirs) > row)):
                    blocked = True
                    break
            if not blocked:
                # How far the pawn has advanced from its own back row (0..7).
                advanced = (7 - row) if is_white else row
                score += PASSED_PAWN_BONUS[advanced]
    return score


# Purpose:  Score one side's rooks for standing on open or semi-open files.
# Args:     rook_squares: squares of that side's rooks.
#           own / enemy: per-file pawn lists, as in _pawn_structure.
# Returns:  The bonus from that side's own point of view.
def _rook_files(rook_squares, own, enemy):
    bonus = 0
    for sq in rook_squares:
        file = sq & 7
        if not own[file]:                       # none of its own pawns in the way
            if not enemy[file]:
                bonus += ROOK_OPEN_FILE_BONUS   # no pawns on the file at all
            else:
                bonus += ROOK_SEMI_OPEN_FILE_BONUS
    return bonus


# ---------------------------------------------------------------------------
# The evaluation
# ---------------------------------------------------------------------------

# Purpose:  Estimate how good the position is for the side to move.
# Args:     board: a board.Board. It is only read, never changed.
# Returns:  An int in centipawns (100 = one pawn). Positive = the side to move is better.
#           Always far below config.MATE_THRESHOLD, so it can never be mistaken for a mate.
def evaluate(board):
    squares = board.squares

    # Everything below is scored from WHITE's point of view, then flipped at the end if
    # Black is the side to move.
    score = 0

    # Facts gathered in the single pass over the board.
    non_pawn_material = 0                    # N+B+R+Q of both sides, decides endgame or not
    white_king = black_king = -1             # -1 = no king (only in artificial test positions)
    white_bishops = black_bishops = 0
    minor_pieces = 0                         # knights + bishops, both sides
    has_pawn_rook_or_queen = False           # if nothing like that exists, mate is impossible
    white_pawns = [[] for _ in range(8)]     # per file: rows of that side's pawns
    black_pawns = [[] for _ in range(8)]
    white_rooks = []
    black_rooks = []

    # One pass over all 64 squares. Material and piece-square values come from the
    # precomputed table; the rest is bookkeeping for the extra terms below.
    for sq in range(64):
        piece = squares[sq]
        if piece == EMPTY:
            continue

        kind = piece if piece > 0 else -piece    # piece type, ignoring colour
        if kind == KING:
            # King squares are scored after the loop, once we know the game phase.
            if piece > 0:
                white_king = sq
            else:
                black_king = sq
            continue

        score += _PIECE_TABLE[piece + 6][sq]

        if kind == PAWN:
            has_pawn_rook_or_queen = True
            (white_pawns if piece > 0 else black_pawns)[sq & 7].append(sq >> 3)
        else:
            non_pawn_material += PIECE_VALUES[kind]
            if kind == BISHOP:
                minor_pieces += 1
                if piece > 0:
                    white_bishops += 1
                else:
                    black_bishops += 1
            elif kind == KNIGHT:
                minor_pieces += 1
            else:                                # rook or queen
                has_pawn_rook_or_queen = True
                if kind == ROOK:
                    (white_rooks if piece > 0 else black_rooks).append(sq)

    # Dead draw: bare kings, or a single knight or bishop against a bare king. Nobody can
    # ever deliver mate, so no amount of "better" placement matters.
    if not has_pawn_rook_or_queen and minor_pieces <= 1:
        return 0

    # King placement: safety in the middlegame, activity in the endgame.
    king_table = (_KING_ENDGAME_TABLE if non_pawn_material <= ENDGAME_MATERIAL_LIMIT
                  else _KING_MIDDLEGAME_TABLE)
    if white_king != -1:
        score += king_table[white_king]
    if black_king != -1:
        score -= king_table[black_king ^ 56]     # flipped, as for any Black piece

    # Bishop pair.
    if white_bishops >= 2:
        score += BISHOP_PAIR_BONUS
    if black_bishops >= 2:
        score -= BISHOP_PAIR_BONUS

    # Pawn structure and rook files, each side scored from its own view and then
    # subtracted (White's good is Black's bad).
    score += _pawn_structure(white_pawns, black_pawns, True)
    score -= _pawn_structure(black_pawns, white_pawns, False)
    score += _rook_files(white_rooks, white_pawns, black_pawns)
    score -= _rook_files(black_rooks, black_pawns, white_pawns)

    # Convert to the side to move's point of view, and add the tempo bonus for it.
    if board.side_to_move == WHITE:
        return score + TEMPO_BONUS
    return TEMPO_BONUS - score


# ---------------------------------------------------------------------------
# Tests: run `python evaluation.py` from the backend folder.
# ---------------------------------------------------------------------------

# Purpose:  Build the mirror image of a position: flip the board upside down, swap every
#           piece's colour, and swap the side to move. A fair evaluation must score the
#           mirror image exactly the same as the original.
def _mirrored(board):
    from board import Board
    mirror = Board(board.to_fen())
    mirror.squares = [-board.squares[sq ^ 56] for sq in range(64)]
    mirror.side_to_move = -board.side_to_move
    return mirror


if __name__ == "__main__":
    from board import Board, START_FEN

    # Purpose:  Evaluate a position given as FEN.
    def ev(fen):
        return evaluate(Board(fen))

    # Perfectly equal position: only the tempo bonus for having the move is left.
    assert ev(START_FEN) == TEMPO_BONUS, ev(START_FEN)

    # The same position seen from Black's side to move gives the same score, and in
    # general the two perspectives add up to exactly two tempo bonuses (the sign flips,
    # the tempo does not).
    for fen in (
        START_FEN,
        "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",          # Black missing its queen
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "4k3/8/8/8/8/8/2PP4/4K3 w - - 0 1",
    ):
        board = Board(fen)
        white_view = evaluate(board)
        board.side_to_move = -board.side_to_move
        black_view = evaluate(board)
        assert white_view + black_view == 2 * TEMPO_BONUS, fen

    # Up a queen is worth about nine pawns for White to move, and about minus nine for
    # Black to move (so the sign really follows the side to move).
    queen_down = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
    assert ev(queen_down + " w KQkq - 0 1") > 800
    assert ev(queen_down + " b KQkq - 0 1") < -800

    # Mirror symmetry on a spread of positions: openings, middlegames, endgames, passed,
    # doubled and isolated pawns, open files. Any asymmetry means a Black-side bug.
    for fen in (
        START_FEN,
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "r2q1rk1/pp2bppp/2n1pn2/2pp4/3P4/2PBPN2/PP3PPP/R1BQ1RK1 b - - 0 9",
        "4k3/pp3p1p/2p5/3P4/8/2N5/PPP2PPP/4K3 w - - 0 1",
        "8/5pk1/6p1/8/3P4/1P2K3/8/8 w - - 0 1",
        "r3k2r/p1pp1ppp/8/1P2P3/8/8/P1P2PPP/R3K2R b KQkq - 0 1",
        "4k3/8/8/8/8/8/PP5P/R3K3 w Q - 0 1",
    ):
        board = Board(fen)
        assert evaluate(board) == evaluate(_mirrored(board)), f"not symmetric: {fen}"

    # Bare kings and a lone minor piece are dead draws.
    assert ev("4k3/8/8/8/8/8/8/4K3 w - - 0 1") == 0
    assert ev("4k3/8/8/8/8/8/8/3NK3 w - - 0 1") == 0
    assert ev("4k3/8/8/8/8/8/8/2B1K3 b - - 0 1") == 0
    assert ev("4k3/8/8/8/8/8/8/R3K3 w - - 0 1") != 0     # a rook can mate

    # Doubled pawns: pawns on a2+a3 versus a2+h3 differ ONLY by the doubled penalty (a3
    # and h3 have equal piece-square values and both layouts are isolated and passed alike).
    doubled = ev("4k3/8/8/8/8/P7/P7/4K3 w - - 0 1")
    spread = ev("4k3/8/8/8/8/7P/P7/4K3 w - - 0 1")
    assert spread - doubled == DOUBLED_PAWN_PENALTY, (spread, doubled)

    # Isolated pawns: a2+b3 are neighbours, a2+g3 are not; equal piece-square totals and
    # equal passed bonuses, so the gap is exactly two isolated penalties.
    connected = ev("4k3/8/8/8/8/1P6/P7/4K3 w - - 0 1")
    isolated = ev("4k3/8/8/8/8/6P1/P7/4K3 w - - 0 1")
    assert connected - isolated == 2 * ISOLATED_PAWN_PENALTY, (connected, isolated)

    # Passed pawn: White's d6 pawn with a Black pawn far away on g7 (d6 is passed) versus a
    # Black pawn on c7 (it stands in d6's way, so d6 is not passed). c7 and g7 have equal
    # piece-square values and are isolated alike, so the gap is exactly: White's passed
    # bonus for a pawn that advanced 5 rows, minus Black's own passed bonus for g7 (1 row).
    passed = ev("4k3/6p1/3P4/8/8/8/8/4K3 w - - 0 1")
    blocked = ev("4k3/2p5/3P4/8/8/8/8/4K3 w - - 0 1")
    assert passed - blocked == PASSED_PAWN_BONUS[5] - PASSED_PAWN_BONUS[1], (passed, blocked)

    # Rook on an open file versus the same rook behind its own pawn (a1 and b1 have the
    # same piece-square value, so the gap is exactly the open-file bonus).
    open_file = ev("4k3/8/8/8/8/8/P7/1R2K3 w - - 0 1")
    closed_file = ev("4k3/8/8/8/8/8/P7/R3K3 w - - 0 1")
    assert open_file - closed_file == ROOK_OPEN_FILE_BONUS, (open_file, closed_file)

    # King safety versus activity. With all pieces on, the king at home beats the king in
    # the open centre; with few pieces left, the centralised king is better.
    assert (ev("rnbqkbnr/8/8/8/8/8/8/RNBQKBNR w - - 0 1")
            > ev("rnbqkbnr/8/8/8/4K3/8/8/RNBQ1BNR w - - 0 1"))
    assert (ev("4k3/8/8/8/4K3/8/8/R7 w - - 0 1")
            > ev("4k3/8/8/8/8/8/8/R3K3 w - - 0 1"))

    # Bishop pair: adding the second bishop (f1) is worth that bishop's material, its
    # piece-square value, and the pair bonus. (A pawn is included in both positions so the
    # single-bishop one is not a dead draw.)
    pair = ev("4k3/8/8/8/8/8/P7/2B1KB2 w - - 0 1")
    single = ev("4k3/8/8/8/8/8/P7/2B1K3 w - - 0 1")
    assert pair - single == PIECE_VALUES[BISHOP] + _BISHOP_TABLE[61] + BISHOP_PAIR_BONUS, (pair, single)

    print("Evaluation tests passed")
