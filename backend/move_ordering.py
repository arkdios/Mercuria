# Purpose:  Search promising moves first, allowing alpha-beta pruning to cut trivial branches.
#           The script assigns priority scores to moves based on tactical factors, such as
#           captures and promotions, then sorts them from highest to lowest priority.
#           It does not decide which move is best or perform the search itself; search.py
#           uses the ordered moves to improve the efficiency of alpha-beta pruning.

from board import (
    BISHOP,
    KING,
    KNIGHT,
    PAWN,
    QUEEN,
    ROOK,
    Board,
    Move,
)

# Piece values are used to prioritize captures.
_PIECE_VALUES = {
    PAWN: 100,
    KNIGHT: 320,
    BISHOP: 330,
    ROOK: 500,
    QUEEN: 900,
    KING: 20_000,
}

# Priority bonuses encourage tactically important moves to be searched first.
_PROMOTION_BONUS = 8_000
_CAPTURE_BONUS = 10_000


# Purpose: Return the piece captured by a move, or 0 if the move is not a capture.
def _get_captured_piece(board, move):
    captured_piece = board.squares[move.to_sq]

    # En passant captures a pawn behind the destination square.
    if (
        captured_piece == 0
        and move.to_sq == board.en_passant_square
        and move.from_sq % 8 != move.to_sq % 8
    ):
        captured_square = move.to_sq + 8 * board.side_to_move
        captured_piece = board.squares[captured_square]

    return captured_piece


# Purpose: Assign a priority score to a move for search ordering.
def _score_move(board, move):
    moving_piece = abs(board.squares[move.from_sq])
    captured_piece = _get_captured_piece(board, move)
    score = 0

    # Captures are prioritized using the victim's and attacker's values.
    if captured_piece:
        victim_value = _PIECE_VALUES[abs(captured_piece)]
        attacker_value = _PIECE_VALUES[moving_piece]

        score += _CAPTURE_BONUS + 10 * victim_value - attacker_value

    # Promotions receive a bonus based on the resulting piece.
    if move.promotion:
        score += _PROMOTION_BONUS + _PIECE_VALUES[abs(move.promotion)]

    return score


# Purpose: Return moves ordered from highest to lowest priority.
def order_moves(board, moves):
    return sorted(
        moves,
        key=lambda move: _score_move(board, move),
        reverse=True,
    )
