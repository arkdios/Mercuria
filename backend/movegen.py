# Purpose: Generate legal moves as well as all special chess rules
#          Two kinds of move lists appear here:
#          * Pseudo-legal moves follow how each piece moves but may
#          leave the mover's own king in check. They are cheap to produce.
#          * Legal moves are the pseudo-legal moves that do not leave the
#          mover's king in check.
#          Special rules handled here: castling (rights, empty squares,
#          and not castling out of, through, or into check), en passant,
#          and promotion to knight, bishop, rook or queen.

from board import (
    BISHOP,
    BLACK,
    BLACK_KINGSIDE,
    BLACK_QUEENSIDE,
    KING,
    KNIGHT,
    PAWN,
    QUEEN,
    ROOK,
    WHITE,
    WHITE_KINGSIDE,
    WHITE_QUEENSIDE,
    Board,
    Move,
    name_to_sq,
)
 
# Steps are written as (row change, column change).
_KNIGHT_STEPS = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
_KING_STEPS = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_ORTHOGONAL_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DIAGONAL_DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
_PROMOTION_PIECES = (QUEEN, ROOK, BISHOP, KNIGHT)
 
# Where each side's pawns start, and the row where they promote.
_PAWN_START_ROW = {WHITE: 6, BLACK: 1}
_PROMOTION_ROW = {WHITE: 0, BLACK: 7}


# Lookup tables that computing it once for all 64 squares
# Purpose: For each square, list the squares reachable by one step in steps (file, rank).
def _build_step_targets(steps):
    table = []

    for square in range(64):
        row, col = divmod(square, 8)
        targets = []

        for row_step, col_step in steps:
            new_row, new_col = row + row_step, col + col_step

            if 0 <= new_row < 8 and 0 <= new_col < 8:
                targets.append(new_row * 8 + new_col)

        table.append(tuple(targets))

    return table

# Purpose: For each square, one ray per direction -> the squares met walking to the board edge.
def _build_rays(directions):
    table = []

    for square in range(64):
        row, col = divmod(square, 8)
        rays = []

        for row_step, col_step in directions:
            ray = []
            new_row, new_col = row + row_step, col + col_step

            while 0 <= new_row < 8 and 0 <= new_col < 8:
                ray.append(new_row * 8 + new_col)
                new_row, new_col = new_row + row_step, new_col + col_step

            rays.append(tuple(ray))

        table.append(tuple(rays))

    return table

# Purpose: For each colour and square, the two diagonal squares a pawn there attacks.
def _build_pawn_capture_targets():
    targets = {WHITE: [], BLACK: []}

    for color, row_step in ((WHITE, -1), (BLACK, 1)):  # White moves toward row 0
        for square in range(64):
            row, col = divmod(square, 8)
            reach = []

            for col_step in (-1, 1):
                new_row, new_col = row + row_step, col + col_step

                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    reach.append(new_row * 8 + new_col)

            targets[color].append(tuple(reach))

    return targets

KNIGHT_TARGETS = _build_step_targets(_KNIGHT_STEPS)
KING_TARGETS = _build_step_targets(_KING_STEPS)
ORTHOGONAL_RAYS = _build_rays(_ORTHOGONAL_DIRECTIONS)
DIAGONAL_RAYS = _build_rays(_DIAGONAL_DIRECTIONS)
PAWN_CAPTURE_TARGETS = _build_pawn_capture_targets()

# Attack detection

# Purpose: Report whether the move just made left the mover's own king in check.
def last_move_left_king_in_check(board: Board) -> bool:
    mover = -board.side_to_move
    return board.is_in_check(mover)


# Move generation

# Purpose: Append the pseudo-legal moves of the pawn on from_square.
def _add_pawn_moves(board: Board, from_square: int, side: int, moves: list, captures_only: bool) -> None:
    squares = board.squares
    forward = -8 * side  # White pawns move toward lower square numbers
    promotion_row = _PROMOTION_ROW[side]
    one_ahead = from_square + forward
 
    # Pushes. Reaching the last rank is tactical, so promotions are kept even
    # when only captures were asked for.
    if squares[one_ahead] == 0:
        if one_ahead // 8 == promotion_row:
            for piece in _PROMOTION_PIECES:
                moves.append(Move(from_square, one_ahead, piece))

        elif not captures_only:
            moves.append(Move(from_square, one_ahead))
            two_ahead = one_ahead + forward

            if from_square // 8 == _PAWN_START_ROW[side] and squares[two_ahead] == 0:
                moves.append(Move(from_square, two_ahead))
 
    # Diagonal captures, including en passant.
    for target in PAWN_CAPTURE_TARGETS[side][from_square]:
        if squares[target] * side < 0 or target == board.en_passant_square:
            if target // 8 == promotion_row:
                for piece in _PROMOTION_PIECES:
                    moves.append(Move(from_square, target, piece))

            else:
                moves.append(Move(from_square, target))

# Purpose: Append castling moves for the side to move.
def _add_castling_moves(board: Board, moves: list) -> None:
    squares = board.squares
    side = board.side_to_move
    enemy = -side
    home = name_to_sq("e1") if side == WHITE else name_to_sq("e8")

    if squares[home] != KING * side:
        return
 
    rights = board.castling_rights
    can_king_side = rights & (WHITE_KINGSIDE if side == WHITE else BLACK_KINGSIDE)
    can_queen_side = rights & (WHITE_QUEENSIDE if side == WHITE else BLACK_QUEENSIDE)

    if not (can_king_side or can_queen_side):
        return
    
    if board.is_square_attacked(home, enemy):
        return  # cannot castle out of check
 
    if (
        can_king_side
        and squares[home + 1] == 0
        and squares[home + 2] == 0
        and not board.is_square_attacked(home + 1, enemy)
        and not board.is_square_attacked(home + 2, enemy)
    ):
        moves.append(Move(home, home + 2))
 
    # The b-file square only needs to be empty. The king never crosses it.
    if (
        can_queen_side
        and squares[home - 1] == 0
        and squares[home - 2] == 0
        and squares[home - 3] == 0
        and not board.is_square_attacked(home - 1, enemy)
        and not board.is_square_attacked(home - 2, enemy)
    ):
        moves.append(Move(home, home - 2))

# Purpose:  Return every pseudo-legal move for the side to move.
# Args:     board: The position.
#           captures_only: If True, return only captures and promotions.
#           The quiescence search uses this to look at forcing moves alone.
# Returns:  A list of encoded move ints. Some may leave the mover's king in check.
def generate_pseudo_legal_moves(board: Board, captures_only: bool = False) -> list:
    squares = board.squares
    side = board.side_to_move
    moves = []
 
    for from_square in range(64):
        piece = squares[from_square]

        if piece * side <= 0:
            continue

        kind = piece * side  # 1..6 whichever colour is moving
 
        if kind == PAWN:
            _add_pawn_moves(board, from_square, side, moves, captures_only)

        elif kind == KNIGHT or kind == KING:
            targets = KNIGHT_TARGETS[from_square] if kind == KNIGHT else KING_TARGETS[from_square]

            for to_square in targets:
                occupant = squares[to_square]

                if occupant * side > 0:
                    continue  # own piece

                if occupant or not captures_only:
                    moves.append(Move(from_square, to_square))
        else:
            rays = []
            if kind != ROOK:
                rays.extend(DIAGONAL_RAYS[from_square])

            if kind != BISHOP:
                rays.extend(ORTHOGONAL_RAYS[from_square])

            for ray in rays:
                for to_square in ray:
                    occupant = squares[to_square]

                    if occupant == 0:
                        if not captures_only:
                            moves.append(Move(from_square, to_square))

                        continue

                    if occupant * side < 0:
                        moves.append(Move(from_square, to_square))

                    break  # a piece blocks the ray, own or enemy
 
    if not captures_only:
        _add_castling_moves(board, moves)

    return moves

# Purpose: Return every legal move for the side to move.
def generate_legal_moves(board: Board) -> list:
    legal = []
    for move in generate_pseudo_legal_moves(board):
        board.make_move(move)

        if not last_move_left_king_in_check(board):
            legal.append(move)

        board.unmake_move()

    return legal