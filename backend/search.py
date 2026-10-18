# Purpose: Implement alpha-beta pruning and Iterative Deepening Depth-First Search

import time
from dataclasses import dataclass
from typing import Optional

from board import Board, Move
from config import (
    INFINITY,
    MATE_SCORE,
    MATE_THRESHOLD,
    MAX_DEPTH,
    MAX_PLY,
    NODE_CHECK_INTERVAL,
)
from evaluation import evaluate
from move_ordering import order_moves
from movegen import generate_pseudo_legal_moves, last_move_left_king_in_check
from transposition_table import (
    EXACT,
    LOWER,
    UPPER,
    TranspositionTable,
    score_from_table,
    score_to_table,
)

# Purpose: Raises inside the search when the time budget runs out.
class SearchTimeout(Exception):
    """Placeholder"""

# Purpose: Switches for the engine's speedups.
@dataclass(frozen=True)
class SearchOptions:
    alpha_beta: bool = True
    move_ordering: bool = True
    transposition_table: bool = True
    quiescence: bool = True

# Purpose: What a finished search reports.
@dataclass(frozen=True)
class SearchResult:
    move: Optional[Move]   # None only when the position has no legal move
    score: int
    depth: int
    nodes: int
    time_ms: int

# Purpose: Searches one position for the best move.
class Searcher:
    # Purpose: Create a searcher that reads and writes ``table``.
    def __init__(self, table: TranspositionTable) -> None:
        self._table = table
        self._options = SearchOptions()
        self._board = None
        self._deadline = 0.0
        self._nodes = 0
        self._killers = [[None, None] for _ in range(MAX_PLY + 1)]

    # Public entry point

    def search(
        self,
        board: Board,
        think_ms: int,
        max_depth: int = MAX_DEPTH,
        options: SearchOptions = SearchOptions(),
    ) -> SearchResult:
        # Find the best move for the side to move.
        self._board = board
        self._options = options
        self._nodes = 0
        started = time.monotonic()
        budget = think_ms / 1000
        self._deadline = started + budget
        undo_depth = len(board.history)

        best_move, best_score, reached_depth = None, 0, 0
        last_pass_seconds = 0.0
        try:
            for depth in range(1, max_depth + 1):
                pass_started = time.monotonic()
                best_move, best_score = self._search_root(depth, best_move)
                reached_depth = depth
                last_pass_seconds = time.monotonic() - pass_started

                if abs(best_score) >= MATE_THRESHOLD:
                    break # a forced mate cannot be improved on

                if (time.monotonic() - started) + last_pass_seconds * 3 > budget:
                    break

        except SearchTimeout:
            pass # the interrupted pass is discarded; keep the last finished one

        finally:
            while len(board.history) > undo_depth:
                board.unmake_move()

        if best_move is None:
            best_move = self._first_legal_move()

        return SearchResult(
            move=best_move,
            score=best_score,
            depth=reached_depth,
            nodes=self._nodes,
            time_ms=int((time.monotonic() - started) * 1000),
        )

    # Search internals
    # Purpose: Count a node, and stop the search if time has run out.
    def _check_clock(self) -> None:
        self._nodes += 1

        if self._nodes & (NODE_CHECK_INTERVAL - 1) == 0 and time.monotonic() >= self._deadline:
            raise SearchTimeout

    # Purpose: Sort moves best-first, unless move ordering is switched off.
    def _sort_moves(self, moves: list, table_move=None, killers: tuple = (None, None)) -> list:
        if not self._options.move_ordering:
            return moves
        
        return order_moves(self._board, moves, table_move, killers)

    # Purpose: Search every legal move at the root to ``depth`` and pick the best.
    def _search_root(self, depth: int, previous_best) -> tuple:
        board = self._board
        moves = self._sort_moves(generate_pseudo_legal_moves(board), previous_best, tuple(self._killers[0]))
        alpha, best_score, best_move = -INFINITY, -INFINITY, None

        for move in moves:
            board.make_move(move)

            if last_move_left_king_in_check(board):
                board.unmake_move()
                continue

            score = -self._negamax(depth - 1, -INFINITY, -alpha, 1)
            board.unmake_move()

            if score > best_score:
                best_score, best_move = score, move

                if self._options.alpha_beta:
                    alpha = max(alpha, score)

        if best_move is None:
            return None, 0
        
        return best_move, best_score

    # Purpose: Score the current position with alpha-beta negamax.
    def _negamax(self, depth: int, alpha: int, beta: int, ply: int) -> int:
        self._check_clock()
        board = self._board

        if board.half_move_clock >= 100:
            return 0
        
        if board.half_move_clock >= 4 and board.repetition_count() >= 2:
            return 0
        
        if ply >= MAX_PLY:
            return evaluate(board)

        side_in_check = board.is_in_check()

        if side_in_check:
            depth += 1 # check extension

        if depth <= 0:
            if self._options.quiescence:
                return self._quiescence(alpha, beta, ply)
            
            return evaluate(board)

        original_alpha = alpha
        table_move = None
        entry = self._table.probe(board.hash) if self._options.transposition_table else None

        if entry is not None:
            stored_depth, flag, stored_score, table_move = entry

            if stored_depth >= depth:
                stored_score = score_from_table(stored_score, ply)

                if flag == EXACT:
                    return stored_score
                
                if flag == LOWER:
                    alpha = max(alpha, stored_score)

                else:
                    beta = min(beta, stored_score)

                if alpha >= beta:
                    return stored_score

        moves = self._sort_moves(generate_pseudo_legal_moves(board), table_move, tuple(self._killers[ply]))
        squares = board.squares
        best_score, best_move, legal_moves = -INFINITY, None, 0

        for move in moves:
            is_quiet = squares[move.to_sq] == 0 and not move.promotion
            board.make_move(move)

            if last_move_left_king_in_check(board):
                board.unmake_move()
                continue

            legal_moves += 1
            score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
            board.unmake_move()

            if score > best_score:
                best_score, best_move = score, move

            if self._options.alpha_beta:
                alpha = max(alpha, score)

                if alpha >= beta:
                    if is_quiet:
                        self._record_killer(ply, move)

                    break

        if legal_moves == 0:
            return -MATE_SCORE + ply if side_in_check else 0

        if best_score <= original_alpha:
            flag = UPPER

        elif best_score >= beta:
            flag = LOWER

        else:
            flag = EXACT

        if self._options.transposition_table:
            self._table.store(board.hash, depth, flag, score_to_table(best_score, ply), best_move)

        return best_score

    # Purpose: Keep playing captures and promotions until the position is quiet.
    def _quiescence(self, alpha: int, beta: int, ply: int) -> int:
        self._check_clock()
        board = self._board
        stand_pat = evaluate(board)

        if ply >= MAX_PLY or stand_pat >= beta:
            return stand_pat
        
        alpha = max(alpha, stand_pat)

        # Respect move ordering options during quiescence search as well
        moves = self._sort_moves(generate_pseudo_legal_moves(board, captures_only=True))

        for move in moves:
            board.make_move(move)

            if last_move_left_king_in_check(board):
                board.unmake_move()
                continue

            score = -self._quiescence(-beta, -alpha, ply + 1)
            board.unmake_move()

            if score >= beta:
                return score
            
            alpha = max(alpha, score)

        return alpha

    # Purpose: Return the first legal move found, or 0 if the position has none.
    def _first_legal_move(self):
        board = self._board

        for move in generate_pseudo_legal_moves(board):
            board.make_move(move)
            illegal = last_move_left_king_in_check(board)
            board.unmake_move()

            if not illegal:
                return move
            
        return None

    # Purpose: Remember a quiet move that caused a cutoff at this ply.
    def _record_killer(self, ply: int, move) -> None:
        slots = self._killers[ply]
        
        if slots[0] != move:
            slots[1] = slots[0]
            slots[0] = move
