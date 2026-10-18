# Purpose:  Board state for the Mercuria chess engine.
#           This module is the single source of truth for a chess position. It stores where
#           the pieces are, whose turn it is, and the extra state chess needs (castling
#           rights, en passant, move counters). It also keeps a Zobrist hash of the position
#           up to date, so the engine can spot repeated positions and use the transposition
#           table. Other modules (movegen, search, evaluation, the API) read from this class
#           or ask it to change. It does NOT generate moves, score positions, or search.
#
# Conventions (these match zobrist.py; every other backend file should use the same ones):
#
#   Pieces        Signed ints. PAWN=1 KNIGHT=2 BISHOP=3 ROOK=4 QUEEN=5 KING=6.
#                 White pieces are positive, Black pieces are negative, 0 is an empty square.
#                 So a black rook is -4 and abs(piece) is always the piece type.
#   Squares       Flat list of 64, numbered from a8:  0 = a8, 7 = h8, 56 = a1, 63 = h1.
#                 row = sq // 8 (row 0 is rank 8), col = sq % 8 (col 0 is the a-file).
#                 This is the order FEN lists the board in. White pawns move toward
#                 LOWER indexes (-8 per step), Black pawns toward HIGHER indexes (+8).
#   Side          WHITE = 1, BLACK = -1. "-side" is always the opponent.
#   Castling      Bitmask 0..15: WHITE_KINGSIDE=1, WHITE_QUEENSIDE=2,
#                 BLACK_KINGSIDE=4, BLACK_QUEENSIDE=8.
#   En passant    The target square index (the square the pawn skipped over), or -1 for none.
#   Moves         Move(from_sq, to_sq, promotion). promotion is 0 for every move except a
#                 pawn promotion, where it is the piece TYPE (KNIGHT..QUEEN, always
#                 positive; the board applies the mover's colour). Castling is a king move
#                 of two squares and en passant is a pawn capture onto the en passant
#                 square; make_move detects both, so moves carry no special flags.

from collections import namedtuple

from zobrist import (
    CASTLING_KEYS,
    EN_PASSANT_KEYS,
    PIECE_KEYS,
    SIDE_KEY,
    hash_position,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMPTY = 0
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6

WHITE = 1
BLACK = -1

WHITE_KINGSIDE = 1
WHITE_QUEENSIDE = 2
BLACK_KINGSIDE = 4
BLACK_QUEENSIDE = 8

# Value of en_passant_square when no en passant capture is available.
NO_SQUARE = -1

# FEN string for the standard chess starting position.
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# FEN letter -> signed piece int, built from the piece order above.
# Uppercase letters are White (positive), lowercase are Black (negative).
CHAR_TO_PIECE = {}
for _type, _letter in enumerate("PNBRQK", start=1):
    CHAR_TO_PIECE[_letter] = _type
    CHAR_TO_PIECE[_letter.lower()] = -_type

# Signed piece int -> FEN letter. The empty square prints as ".".
PIECE_TO_CHAR = {piece: letter for letter, piece in CHAR_TO_PIECE.items()}
PIECE_TO_CHAR[EMPTY] = "."

# FEN castling letter -> bit, in the order FEN writes them ("KQkq").
CASTLING_CHARS = (
    ("K", WHITE_KINGSIDE),
    ("Q", WHITE_QUEENSIDE),
    ("k", BLACK_KINGSIDE),
    ("q", BLACK_QUEENSIDE),
)

# Promotion letter in a move string ("e7e8q") -> piece type.
PROMOTION_CHAR_TO_TYPE = {"n": KNIGHT, "b": BISHOP, "r": ROOK, "q": QUEEN}

# Row/column steps used by the attack check.
KNIGHT_OFFSETS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KING_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
ROOK_DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
BISHOP_DIRECTIONS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

# A move is described by where it starts, where it ends, and (only for pawn
# promotion) which piece type the pawn becomes. See the conventions above.
Move = namedtuple("Move", ["from_sq", "to_sq", "promotion"], defaults=[0])

# Everything unmake_move needs to restore, saved by make_move.
#   captured / captured_sq: the piece taken and the square it stood on. These differ from
#   to_sq only for en passant. The remaining fields are the old game state.
_Undo = namedtuple(
    "_Undo",
    [
        "move", "piece", "captured", "captured_sq",
        "castling_rights", "en_passant_square",
        "half_move_clock", "full_move_number", "hash",
    ],
)


# ---------------------------------------------------------------------------
# Square and move helpers
# ---------------------------------------------------------------------------

# Purpose:  Convert a square index (0-63) to algebraic notation.
#           Example: sq_to_name(0) -> "a8", sq_to_name(36) -> "e4".
def sq_to_name(sq):
    file_letter = "abcdefgh"[sq % 8]   # the column picks the letter
    rank_number = 8 - sq // 8          # row 0 is rank 8, so count down
    return file_letter + str(rank_number)


# Purpose:  Convert algebraic notation to a square index (0-63). Inverse of sq_to_name.
#           Example: name_to_sq("a8") -> 0, name_to_sq("e4") -> 36.
def name_to_sq(name):
    col = "abcdefgh".index(name[0])    # letter -> column 0-7
    row = 8 - int(name[1])             # rank 8 is row 0, rank 1 is row 7
    return row * 8 + col


# Purpose:  Turn a Move into coordinate text such as "e2e4" or "e7e8q".
def move_to_uci(move):
    text = sq_to_name(move.from_sq) + sq_to_name(move.to_sq)
    if move.promotion:
        text += "nbrq"[move.promotion - KNIGHT]
    return text


# Purpose:  Turn coordinate text such as "e2e4" or "e7e8q" into a Move.
#           This is the format a browser would most naturally send.
# Raises:   ValueError / KeyError / IndexError if the text is malformed.
def uci_to_move(text):
    promotion = PROMOTION_CHAR_TO_TYPE[text[4].lower()] if len(text) == 5 else 0
    return Move(name_to_sq(text[0:2]), name_to_sq(text[2:4]), promotion)


# For each square, which castling rights SURVIVE a move that starts or ends there.
# Moving the king or a rook from its home square, or capturing a rook on its home
# square, removes the matching rights. Every other square keeps all rights (15).
_CASTLING_KEEP = [15] * 64
_CASTLING_KEEP[name_to_sq("e1")] = 15 & ~(WHITE_KINGSIDE | WHITE_QUEENSIDE)
_CASTLING_KEEP[name_to_sq("h1")] = 15 & ~WHITE_KINGSIDE
_CASTLING_KEEP[name_to_sq("a1")] = 15 & ~WHITE_QUEENSIDE
_CASTLING_KEEP[name_to_sq("e8")] = 15 & ~(BLACK_KINGSIDE | BLACK_QUEENSIDE)
_CASTLING_KEEP[name_to_sq("h8")] = 15 & ~BLACK_KINGSIDE
_CASTLING_KEEP[name_to_sq("a8")] = 15 & ~BLACK_QUEENSIDE


# ---------------------------------------------------------------------------
# The board
# ---------------------------------------------------------------------------

class Board:
    """A chess position, its Zobrist hash, and the history needed to undo moves.

    Attributes:
        squares: list of 64 signed piece ints (see the conventions at the top).
        side_to_move: WHITE (1) or BLACK (-1).
        castling_rights: bitmask 0..15 of the castling rights still available.
        en_passant_square: square index a pawn may capture onto this turn, or -1.
        half_move_clock: half-moves since the last capture or pawn move (50-move rule).
        full_move_number: starts at 1 and goes up after Black moves.
        hash: 64-bit Zobrist hash of the position, kept current by make/unmake.
        history: stack of _Undo records, one per move played with make_move.
    """

    # Purpose:  Create a board. With no argument it holds the starting position.
    # Args:     fen: FEN string to load, or START_FEN by default.
    def __init__(self, fen=START_FEN):
        self.squares = [EMPTY] * 64
        self.side_to_move = WHITE
        self.castling_rights = 0
        self.en_passant_square = NO_SQUARE
        self.half_move_clock = 0
        self.full_move_number = 1
        self.hash = 0
        self.history = []
        self.from_fen(fen)

    # Purpose:  Return the board as a text grid, rank 8 at the top. For debugging.
    def __str__(self):
        rows = []
        for r in range(8):
            rank = 8 - r  # row 0 is rank 8
            letters = [PIECE_TO_CHAR[p] for p in self.squares[r * 8:(r + 1) * 8]]
            rows.append(f"{rank} " + " ".join(letters))
        rows.append("  a b c d e f g h")  # file labels along the bottom
        return "\n".join(rows)

    # -- FEN ---------------------------------------------------------------

    # Purpose:  Load a position from a FEN string, replacing the current state.
    #           Clears the move history, since it belongs to the old position, and
    #           recomputes the hash from scratch.
    # Args:     fen: a six-field FEN string, e.g. START_FEN.
    # Raises:   ValueError if the FEN does not have six fields or the piece placement
    #           does not describe exactly 64 squares.
    def from_fen(self, fen):
        fields = fen.split()
        if len(fields) != 6:
            raise ValueError(f"FEN needs 6 fields, got {len(fields)}: {fen!r}")
        placement, side, castling, ep, half_move, full_move = fields

        # Field 1: piece placement. FEN lists rank 8 first, left to right, which is
        # exactly our square order, so we can just count upward.
        squares = [EMPTY] * 64
        sq = 0
        for ch in placement:
            if ch == "/":
                continue                    # rank separator; sq is already at the next rank
            elif ch.isdigit():
                sq += int(ch)               # a digit means that many empty squares
            else:
                if sq > 63 or ch not in CHAR_TO_PIECE:
                    raise ValueError(f"bad FEN piece placement: {placement!r}")
                squares[sq] = CHAR_TO_PIECE[ch]
                sq += 1
        if sq != 64:
            raise ValueError(f"FEN piece placement covers {sq} squares, not 64")

        # Fields 2-6: convert the text into the engine's encodings.
        self.squares = squares
        self.side_to_move = WHITE if side == "w" else BLACK
        self.castling_rights = sum(bit for letter, bit in CASTLING_CHARS if letter in castling)
        self.en_passant_square = NO_SQUARE if ep == "-" else name_to_sq(ep)
        self.half_move_clock = int(half_move)
        self.full_move_number = int(full_move)
        self.history = []
        self.hash = hash_position(
            self.squares, self.side_to_move, self.castling_rights, self.en_passant_square
        )

    # Purpose:  Return the current position as a FEN string. Inverse of from_fen:
    #           loading a FEN and exporting it gives back the same string.
    def to_fen(self):
        # Field 1: build each rank, compressing runs of empty squares into a digit.
        rank_strings = []
        for r in range(8):
            text = ""
            empty_run = 0
            for piece in self.squares[r * 8:(r + 1) * 8]:
                if piece == EMPTY:
                    empty_run += 1
                else:
                    if empty_run:               # flush the pending run of empties
                        text += str(empty_run)
                        empty_run = 0
                    text += PIECE_TO_CHAR[piece]
            if empty_run:                       # the rank ended with empty squares
                text += str(empty_run)
            rank_strings.append(text)
        placement = "/".join(rank_strings)

        # Fields 2-6. FEN writes "-" when there are no castling rights / no en passant.
        side = "w" if self.side_to_move == WHITE else "b"
        castling = "".join(l for l, bit in CASTLING_CHARS if self.castling_rights & bit) or "-"
        ep = "-" if self.en_passant_square == NO_SQUARE else sq_to_name(self.en_passant_square)
        return f"{placement} {side} {castling} {ep} {self.half_move_clock} {self.full_move_number}"

    # -- Simple queries ----------------------------------------------------

    # Purpose:  Return the signed piece int on a square (EMPTY = 0 if none).
    def piece_at(self, sq):
        return self.squares[sq]

    # Purpose:  Find a side's king.
    # Args:     color: WHITE or BLACK.
    # Returns:  The king's square index, or NO_SQUARE (-1) if that side has no king
    #           (only possible in artificial test positions).
    def find_king(self, color):
        try:
            return self.squares.index(color * KING)
        except ValueError:
            return NO_SQUARE

    # Purpose:  Is a square attacked by any piece of the given side?
    #           movegen uses this to throw out moves that leave the mover's king in
    #           check, and to validate castling. It looks OUTWARD from the square: pawn
    #           diagonals, knight jumps, king neighbours, then slides along each line
    #           until it hits a piece. The square itself may be empty or occupied.
    # Args:     sq: square index to test. by_color: WHITE or BLACK, the attacker.
    def is_square_attacked(self, sq, by_color):
        squares = self.squares
        row, col = divmod(sq, 8)

        # Pawns. A White pawn attacks toward lower rows, so an attacking White pawn
        # stands one row BELOW (row + 1) the target; a Black attacker is at row - 1.
        pawn_row = row + by_color
        if 0 <= pawn_row < 8:
            for dc in (-1, 1):
                c = col + dc
                if 0 <= c < 8 and squares[pawn_row * 8 + c] == by_color * PAWN:
                    return True

        # Knights.
        for dr, dc in KNIGHT_OFFSETS:
            r, c = row + dr, col + dc
            if 0 <= r < 8 and 0 <= c < 8 and squares[r * 8 + c] == by_color * KNIGHT:
                return True

        # Kings (an enemy king one step away also attacks the square).
        for dr, dc in KING_OFFSETS:
            r, c = row + dr, col + dc
            if 0 <= r < 8 and 0 <= c < 8 and squares[r * 8 + c] == by_color * KING:
                return True

        # Sliding pieces: walk outward until the first piece in the way.
        # Straight lines can be hit by a rook or queen, diagonals by a bishop or queen.
        for directions, slider in ((ROOK_DIRECTIONS, ROOK), (BISHOP_DIRECTIONS, BISHOP)):
            for dr, dc in directions:
                r, c = row + dr, col + dc
                while 0 <= r < 8 and 0 <= c < 8:
                    piece = squares[r * 8 + c]
                    if piece != EMPTY:
                        if piece == by_color * slider or piece == by_color * QUEEN:
                            return True
                        break           # blocked by some other piece
                    r += dr
                    c += dc
        return False

    # Purpose:  Is a side's king in check?
    # Args:     color: WHITE or BLACK; defaults to the side to move.
    def is_in_check(self, color=None):
        if color is None:
            color = self.side_to_move
        king_sq = self.find_king(color)
        if king_sq == NO_SQUARE:
            return False
        return self.is_square_attacked(king_sq, -color)

    # Purpose:  How many times has the current position occurred, counting now?
    #           Returns 3+ when a threefold-repetition draw can be claimed. The hash
    #           includes side to move, castling rights and en passant, so equal hashes
    #           mean the same position. Only the last half_move_clock plies are checked,
    #           because a capture or pawn move makes earlier positions unreachable.
    #           Positions from before from_fen was called are unknown, so a game replayed
    #           from the start (as the API does) gets exact counts.
    def repetition_count(self):
        count = 1
        lookback = min(self.half_move_clock, len(self.history))
        for undo in self.history[len(self.history) - lookback:]:
            if undo.hash == self.hash:
                count += 1
        return count

    # -- Making and unmaking moves -----------------------------------------

    # Purpose:  Play a move, update the hash incrementally, and save what unmake_move
    #           needs. Handles every kind of move: quiet moves, captures, promotion,
    #           castling (the rook moves too), en passant (the captured pawn is not on
    #           the destination square), castling-rights loss, and setting the en passant
    #           square after a double pawn push.
    # Args:     move: a Move. It is assumed legal; legality is movegen's job, not ours.
    def make_move(self, move):
        from_sq, to_sq, promotion = move
        color = self.side_to_move
        squares = self.squares
        piece = squares[from_sq]
        captured = squares[to_sq]
        captured_sq = to_sq

        # En passant: a pawn captures diagonally onto the (empty) en passant square. The
        # pawn being captured sits one step BEHIND that square, from the mover's view.
        if (abs(piece) == PAWN and to_sq == self.en_passant_square
                and captured == EMPTY and from_sq % 8 != to_sq % 8):
            captured_sq = to_sq + 8 * color
            captured = squares[captured_sq]

        # Save the old state BEFORE changing anything.
        self.history.append(_Undo(
            move, piece, captured, captured_sq,
            self.castling_rights, self.en_passant_square,
            self.half_move_clock, self.full_move_number, self.hash,
        ))

        # Each block below changes the board and XORs the same facts in or out of the hash.
        h = self.hash

        # Lift the moving piece off its origin square.
        h ^= PIECE_KEYS[piece + 6][from_sq]
        squares[from_sq] = EMPTY

        # Remove a captured piece (on to_sq, or behind it for en passant).
        if captured != EMPTY:
            h ^= PIECE_KEYS[captured + 6][captured_sq]
            squares[captured_sq] = EMPTY

        # Put the piece down. A promoting pawn becomes the chosen piece in the mover's colour.
        placed = color * promotion if promotion else piece
        squares[to_sq] = placed
        h ^= PIECE_KEYS[placed + 6][to_sq]

        # Castling: the king moved two squares, so also move the rook next to it.
        # Kingside (to the right) the rook jumps from 3 squares right of the king to just
        # left of its landing square; queenside it comes from 4 squares left.
        if abs(piece) == KING and abs(to_sq - from_sq) == 2:
            if to_sq > from_sq:
                rook_from, rook_to = from_sq + 3, from_sq + 1
            else:
                rook_from, rook_to = from_sq - 4, from_sq - 1
            rook = squares[rook_from]
            squares[rook_from] = EMPTY
            squares[rook_to] = rook
            h ^= PIECE_KEYS[rook + 6][rook_from] ^ PIECE_KEYS[rook + 6][rook_to]

        # Castling rights: remove any lost because of the squares this move touched.
        old_rights = self.castling_rights
        new_rights = old_rights & _CASTLING_KEEP[from_sq] & _CASTLING_KEEP[to_sq]
        h ^= CASTLING_KEYS[old_rights] ^ CASTLING_KEYS[new_rights]
        self.castling_rights = new_rights

        # En passant: the old opportunity expires; a double pawn push creates a new one
        # on the square it skipped over (halfway between from and to).
        if self.en_passant_square != NO_SQUARE:
            h ^= EN_PASSANT_KEYS[self.en_passant_square & 7]
        if abs(piece) == PAWN and abs(to_sq - from_sq) == 16:
            self.en_passant_square = (from_sq + to_sq) // 2
            h ^= EN_PASSANT_KEYS[self.en_passant_square & 7]
        else:
            self.en_passant_square = NO_SQUARE

        # Clocks: the half-move clock resets on a pawn move or capture; the full-move
        # number goes up after Black moves.
        if abs(piece) == PAWN or captured != EMPTY:
            self.half_move_clock = 0
        else:
            self.half_move_clock += 1
        if color == BLACK:
            self.full_move_number += 1

        # Hand the turn to the other side.
        self.side_to_move = -color
        h ^= SIDE_KEY

        self.hash = h

    # Purpose:  Undo the most recent make_move, restoring the exact previous state
    #           (including the hash). After make_move then unmake_move, to_fen() and
    #           hash are identical to before. Search depends on this being perfect.
    def unmake_move(self):
        undo = self.history.pop()
        from_sq, to_sq, _ = undo.move
        squares = self.squares

        # Clear the destination first, then put the mover back on its origin square.
        # (A promoted piece is replaced by the original pawn here.)
        squares[to_sq] = EMPTY
        squares[from_sq] = undo.piece

        # Restore any captured piece to the square it stood on (not to_sq for en passant).
        if undo.captured != EMPTY:
            squares[undo.captured_sq] = undo.captured

        # Castling: move the rook back to its corner.
        if abs(undo.piece) == KING and abs(to_sq - from_sq) == 2:
            if to_sq > from_sq:
                rook_from, rook_to = from_sq + 3, from_sq + 1
            else:
                rook_from, rook_to = from_sq - 4, from_sq - 1
            squares[rook_from] = squares[rook_to]
            squares[rook_to] = EMPTY

        # Restore the saved game state. The side to move simply flips back.
        self.side_to_move = -self.side_to_move
        self.castling_rights = undo.castling_rights
        self.en_passant_square = undo.en_passant_square
        self.half_move_clock = undo.half_move_clock
        self.full_move_number = undo.full_move_number
        self.hash = undo.hash


# ---------------------------------------------------------------------------
# Tests: run `python board.py` from the backend folder.
# ---------------------------------------------------------------------------

# Purpose:  Make one move from a FEN and check three things: the resulting FEN is what
#           we expect, the incrementally updated hash equals a from-scratch hash, and
#           unmaking restores the original FEN and hash exactly.
def _check_move(board, fen, uci, expected_fen):
    board.from_fen(fen)
    original_hash = board.hash

    board.make_move(uci_to_move(uci))
    assert board.to_fen() == expected_fen, f"{uci}: got {board.to_fen()}"
    fresh = hash_position(
        board.squares, board.side_to_move, board.castling_rights, board.en_passant_square
    )
    assert board.hash == fresh, f"{uci}: incremental hash does not match a fresh hash"

    board.unmake_move()
    assert board.to_fen() == fen, f"{uci}: unmake did not restore the FEN"
    assert board.hash == original_hash, f"{uci}: unmake did not restore the hash"


if __name__ == "__main__":
    b = Board()
    print(b)  # the standard starting position
    assert b.to_fen() == START_FEN, "FEN round trip failed"

    # Square helpers: a8 is 0, h1 is 63, e4 is 36.
    assert (sq_to_name(0), sq_to_name(63), name_to_sq("e4")) == ("a8", "h1", 36)
    assert move_to_uci(uci_to_move("e7e8q")) == "e7e8q"
    print("FEN and helper tests passed")

    # Quiet move and double pawn push (sets the en passant square), White then Black.
    _check_move(b, START_FEN, "e2e4",
                "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    _check_move(b, "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", "e7e5",
                "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2")

    # Ordinary capture.
    _check_move(b, "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2", "e4d5",
                "rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2")

    # Castling, all four ways. The king move also costs that side both its rights.
    both_sides = "r3k2r/8/8/8/8/8/8/R3K2R"
    _check_move(b, both_sides + " w KQkq - 0 1", "e1g1", "r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1")
    _check_move(b, both_sides + " w KQkq - 0 1", "e1c1", "r3k2r/8/8/8/8/8/8/2KR3R b kq - 1 1")
    _check_move(b, both_sides + " b KQkq - 0 1", "e8g8", "r4rk1/8/8/8/8/8/8/R3K2R w KQ - 1 2")
    _check_move(b, both_sides + " b KQkq - 0 1", "e8c8", "2kr3r/8/8/8/8/8/8/R3K2R w KQ - 1 2")

    # Taking a rook on its home square removes both sides' queenside rights.
    _check_move(b, both_sides + " w KQkq - 0 1", "a1a8", "R3k2r/8/8/8/8/8/8/4K2R b Kk - 0 1")

    # En passant, for each colour: the captured pawn is NOT on the destination square.
    _check_move(b, "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6", "4k3/8/3P4/8/8/8/8/4K3 b - - 0 1")
    _check_move(b, "4k3/8/8/8/3pP3/8/8/4K3 b - e3 0 1", "d4e3", "4k3/8/8/8/8/4p3/8/4K3 w - - 0 2")

    # Promotion, including with a capture, an under-promotion and a Black promotion.
    _check_move(b, "4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8q", "Q3k3/8/8/8/8/8/8/4K3 b - - 0 1")
    _check_move(b, "1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7b8n", "1N2k3/8/8/8/8/8/8/4K3 b - - 0 1")
    _check_move(b, "4k3/8/8/8/8/8/p7/4K3 b - - 0 1", "a2a1q", "4k3/8/8/8/8/8/8/q3K3 w - - 0 2")
    print("Move tests passed")

    # Attack and check detection: sliders, blocking, knights, pawns of both colours.
    b.from_fen(START_FEN)
    assert b.is_square_attacked(name_to_sq("f3"), WHITE)      # guarded by e2, g2, Ng1
    assert not b.is_square_attacked(name_to_sq("e4"), WHITE)  # nobody reaches e4 yet
    assert b.is_square_attacked(name_to_sq("e6"), BLACK)      # guarded by d7, f7
    assert not b.is_in_check()
    for fen, in_check in [
        ("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1", True),    # rook gives check
        ("4k3/8/8/8/4r3/8/4P3/4K3 w - - 0 1", False), # the pawn on e2 blocks the rook
        ("4k3/8/8/8/8/5n2/8/4K3 w - - 0 1", True),    # knight check
        ("4k3/8/8/8/8/8/3p4/4K3 w - - 0 1", True),    # Black pawn check
        ("4k3/3P4/8/8/8/8/8/4K3 b - - 0 1", True),    # White pawn check on Black
        ("4k3/8/8/8/7b/8/8/4K3 w - - 0 1", True),     # bishop on h4 checks along h4-e1
    ]:
        b.from_fen(fen)
        assert b.is_in_check() == in_check, f"check detection wrong for {fen}"
    print("Attack tests passed")

    # Repetition: shuffling knights returns to the start position every 4 plies.
    b.from_fen(START_FEN)
    cycle = [uci_to_move(m) for m in ("g1f3", "g8f6", "f3g1", "f6g8")]
    for move in cycle:
        b.make_move(move)
    assert b.repetition_count() == 2
    for move in cycle:
        b.make_move(move)
    assert b.repetition_count() == 3
    print("Repetition test passed")