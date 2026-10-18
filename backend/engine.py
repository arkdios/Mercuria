# Purpose: Single entry point between the API and the chess code: replays a game, reports its status, and picks the bot's reply

from board import BISHOP, BLACK, KING, KNIGHT, WHITE, Board, move_to_uci, sq_to_name, uci_to_move
from config import DEFAULT_THINK_MS, MAX_THINK_MS, MIN_THINK_MS, TT_MAX_ENTRIES, MAX_DEPTH
from movegen import generate_legal_moves
from search import Searcher, SearchOptions
from transposition_table import TranspositionTable

# Game status values returned to the frontend.
STATUS_ONGOING = "ongoing"
STATUS_CHECKMATE = "checkmate"
STATUS_STALEMATE = "stalemate"
STATUS_DRAW_REPETITION = "draw_repetition"
STATUS_DRAW_FIFTY_MOVE = "draw_fifty_move"
STATUS_DRAW_INSUFFICIENT = "draw_insufficient_material"

# Purpose: Replay UCI moves from the starting position.
# Args: moves: UCI move strings, oldest first.
# Returns: The resulting board, with its full history.
# Raises: ValueError: If any move is malformed or illegal in its position.
def board_from_moves(moves: list) -> Board:
    board = Board()

    for ply, text in enumerate(moves, start=1):
        move = uci_to_move(text)
        if move not in generate_legal_moves(board):
            raise ValueError(f"illegal move {text!r} at half-move {ply}")
        
        board.make_move(move)
    return board

# Purpose: Can neither side possibly deliver checkmate? True for bare kings, or one knight or bishop against a bare king.
def has_insufficient_material(board: Board) -> bool:
    minors = 0
    for piece in board.squares:
        kind = abs(piece)
        if kind == 0 or kind == KING:
            continue
        if kind == KNIGHT or kind == BISHOP:
            minors += 1
        else:
            return False
    return minors <= 1

# Purpose: Classify the position as ongoing, checkmate, stalemate, or a draw.
# Args: board: The position.
#       legal_moves: The legal moves for the side to move (computed once by the caller).
# Returns: One of the STATUS_* constants.
def game_status(board: Board, legal_moves: list) -> str:
    if not legal_moves:
        return STATUS_CHECKMATE if board.is_in_check() else STATUS_STALEMATE
    if board.repetition_count() >= 3:
        return STATUS_DRAW_REPETITION
    if board.half_move_clock >= 100:
        return STATUS_DRAW_FIFTY_MOVE
    if has_insufficient_material(board):
        return STATUS_DRAW_INSUFFICIENT
    return STATUS_ONGOING

# Purpose: Summarise a position for the frontend.
# Returns: A JSON-ready dict
def describe_position(board: Board) -> dict:
    legal_moves = generate_legal_moves(board)
    status = game_status(board, legal_moves)
    checked = board.is_in_check()
    winner = None

    if status == STATUS_CHECKMATE:
        winner = "w" if board.side_to_move == BLACK else "b"

    return {
        "fen": board.to_fen(),
        "turn": "w" if board.side_to_move == WHITE else "b",
        "legal_moves": [move_to_uci(m) for m in legal_moves],
        "in_check": checked,
        "check_square": sq_to_name(board.find_king(board.side_to_move)) if checked else None,
        "status": status,
        "winner": winner,
    }

# Purpose: Replays games and chooses moves. Holds one transposition table shared by all searches.
class Engine:
    # Purpose: Create an engine with an empty transposition table.
    def __init__(self) -> None:
        self._table = TranspositionTable(TT_MAX_ENTRIES)

    # Purpose: Describe the position after moves. Raises ValueError on an illegal move.
    def position(self, moves: list) -> dict:
        return describe_position(board_from_moves(moves))

    # Purpose: Choose and play the bot's reply to the position after moves.
    # Args: moves: UCI moves played so far, oldest first.
    #       think_ms: Thinking time in milliseconds. Clamped to the configured range.
    #       options: Which speedups the search may use (all on by default).
    # Returns: A dict
    # Raises: ValueError: If a move is illegal, or the game is already over.
    def bot_move(self, moves: list, think_ms: int = DEFAULT_THINK_MS, options: SearchOptions = SearchOptions(),) -> dict:
        board = board_from_moves(moves)
        legal_moves = generate_legal_moves(board)

        if game_status(board, legal_moves) != STATUS_ONGOING:
            raise ValueError("the game is already over")

        think_ms = max(MIN_THINK_MS, min(MAX_THINK_MS, think_ms))
        result = Searcher(self._table).search(board, think_ms, MAX_DEPTH, options=options)
        board.make_move(result.move)

        return {
            "move": move_to_uci(result.move),
            "score": result.score,
            "depth": result.depth,
            "nodes": result.nodes,
            "time_ms": result.time_ms,
            "position": describe_position(board),
        }