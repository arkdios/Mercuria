/// Purpose: Coordinates the game, connects the board to the API, and updates the interface
///          The backend is the only place that knows the chess rules. This file never
///          decides whether a move is legal. It only uses the list the backend sends.

import { ApiError, fetchBotMove, fetchPosition, ping } from "./api.js";
import { BOARD_STYLES, applyBoardStyle, createBoardView, parsePieces } from "./board.js";

//  Scores at or beyond this many centipawns mean "forced checkmate".
const MATE_LIMIT = 99000;

//  Everything the page remembers about the current game

const state = {
    moves: [], // every move played so far, like ["e2e4", "e7e5"]
    position: null, // the backend's description of the current position
    pieces: {}, // square name -> piece code, for drawing
    playerColor: "w", // "w" or "b": the side the human plays
    legalByFrom: {}, // from-square -> list of legal move strings that start there
    selected: null, // the square the player has clicked, if any
    lastMove: [], // [from, to] of the previous move, for highlighting
    busy: false, // true while we wait for the backend
    pendingPromotion: null, // [from, to] while the player picks a promotion piece
};

//  Page elements

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const retryButton = $("retry");
const newGameButton = $("new-game");
const playerColorSelect = $("player-color");
const promotionEl = $("promotion");
const boardElement = $("board");
const board = createBoardView(boardElement, handleSquareClick);

//  Small helpers

/** Purpose: Show a message in the status line. */
function setStatus(message, isError = false) {
    statusEl.textContent = message;
    statusEl.classList.toggle("is-error", isError);
}

/** Purpose: True when it is the human's turn in a game that is still going. */
function isPlayersTurn() {
    return state.position !== null && state.position.status === "ongoing" && state.position.turn === state.playerColor;
}

/** Purpose: Turn the backend's list of legal moves into a lookup by starting square. */
function indexLegalMoves(legalMoves) {
    const byFrom = {};
    for (const move of legalMoves) {
        const from = move.slice(0, 2);
        (byFrom[from] ||= []).push(move);
    }
    return byFrom;
}

/** Purpose: The squares the selected piece may move to (promotion choices count once). */
function currentTargets() {
    if (!state.selected || !state.legalByFrom[state.selected]) {
        return [];
    }
    return [...new Set(state.legalByFrom[state.selected].map((move) => move.slice(2, 4)))];
}

const THINK_MIN_SECONDS = 0.5;
const THINK_MAX_SECONDS = 10; // must match MAX_THINK_MS in backend/config.py
const THINK_DEFAULT_SECONDS = 4;

/**
 *  Purpose: Read the thinking time the player typed, in seconds, and return it in milliseconds.
 */
function readThinkMs() {
    const input = $("think-time");
    let seconds = Number(input.value);

    if (input.value.trim() === "" || !Number.isFinite(seconds)) {
        seconds = THINK_DEFAULT_SECONDS;
    }

    seconds = Math.min(THINK_MAX_SECONDS, Math.max(THINK_MIN_SECONDS, seconds));
    input.value = String(seconds);
    return Math.round(seconds * 1000);
}

/** Purpose: Read the three on/off switches from the Engine lab. */
function readFeatureSwitches() {
    return {
        alpha_beta: $("feature-alpha-beta").checked,
        move_ordering: $("feature-move-ordering").checked,
        transposition_table: $("feature-transposition-table").checked,
    };
}

/** Purpose: Make the status line say what is going on and whose turn it is. */
function describeGameState() {
    const position = state.position;
    if (position.status === "checkmate") {
        return position.winner === state.playerColor ? "Checkmate. You win!" : "Checkmate. Mercuria wins.";
    }

    const draws = {
        stalemate: "Draw by stalemate: the side to move has no legal move but is not in check.",
        draw_repetition: "Draw: the same position happened three times.",
        draw_fifty_move: "Draw: fifty moves passed with no capture or pawn move.",
        draw_insufficient_material: "Draw: neither side has enough pieces to checkmate.",
    };

    if (draws[position.status]) {
        return draws[position.status];
    }

    const check = position.in_check ? " Check!" : "";
    return isPlayersTurn() ? `Your move.${check}` : `Mercuria is thinking…${check}`;
}

/** Purpose: Format the engine's score for people: "+0.35 for Mercuria", "Mate for you", and so on. */
function formatEvaluation(score) {
    if (score >= MATE_LIMIT) {
        return "Mate for Mercuria";
    }

    if (score <= -MATE_LIMIT) {
        return "Mate for you";
    }

    const pawns = (score / 100).toFixed(2);
    return score >= 0 ? `+${pawns} for Mercuria` : `${pawns} for you`;
}

/** Purpose: Fill in the "What the engine just did" numbers. */
function showEngineReadout(reply) {
    const seconds = reply.time_ms / 1000;
    $("stat-depth").textContent = reply.depth;
    $("stat-nodes").textContent = reply.nodes.toLocaleString();
    $("stat-time").textContent = `${seconds.toFixed(2)} s`;
    $("stat-speed").textContent = seconds > 0 ? `${Math.round(reply.nodes / seconds).toLocaleString()} per second` : "–";
    $("stat-eval").textContent = formatEvaluation(reply.score);
}

/** Purpose: Rebuild the numbered move list. */
function renderMoveList() {
    const list = $("move-list");
    list.replaceChildren();

    for (let i = 0; i < state.moves.length; i += 2) {
        const item = document.createElement("li");
        const white = state.moves[i];
        const black = state.moves[i + 1] || "";
        item.textContent = `${white}  ${black}`.trim();
        list.appendChild(item);
    }
}

//  Drawing everything

/** Purpose: Redraw the board, status line, buttons and move list from the current state. */
function renderAll() {
    board.render({
        pieces: state.pieces,
        orientation: state.playerColor,
        selected: state.selected,
        targets: currentTargets(),
        lastMove: state.lastMove,
        checkSquare: state.position ? state.position.check_square : null,
    });

    if (state.position && !state.busy) {
        setStatus(describeGameState());
    }

    newGameButton.disabled = state.busy;
    playerColorSelect.disabled = state.busy;
    promotionEl.hidden = state.pendingPromotion === null;
    renderMoveList();
}

/** Purpose: Store a new position from the backend, then redraw. */
function applyPosition(position) {
    state.position = position;
    state.pieces = parsePieces(position.fen);
    state.legalByFrom = indexLegalMoves(position.legal_moves);
    state.selected = null;
    state.pendingPromotion = null;
    const lastUci = state.moves[state.moves.length - 1];
    state.lastMove = lastUci ? [lastUci.slice(0, 2), lastUci.slice(2, 4)] : [];
    renderAll();
}

//  Talking to the backend

/** Pupose: Show a plain-language error and let the player retry the action that failed. */
function showError(error, retryAction) {
    const message = error instanceof ApiError ? error.message : "Something unexpected went wrong.";
    setStatus(message, true);
    retryButton.hidden = false;

    retryButton.onclick = () => {
        retryButton.hidden = true;
        retryAction();
    };
}

/**
 *  Purpose: Run an async action while showing a message and blocking the controls.
 *           Controls stay blocked until the action finishes or fails, so two requests
 *           can never overlap.
 */
async function whileBusy(message, action) {
    state.busy = true;
    retryButton.hidden = true;
    setStatus(message);
    renderAll();

    try {
        await action();
    } finally {
        state.busy = false;
        renderAll();
    }
}

/** Purpose: Free servers fall asleep. Ping until the backend answers, telling the player what is happening. */
async function waitForBackend() {
    const maxAttempts = 20;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            await ping();
            return;
        } catch (error) {
            setStatus(`Waking up the engine (attempt ${attempt} of ${maxAttempts}). Free servers sleep when idle, so this can take a minute.`);
            await new Promise((resolve) => setTimeout(resolve, 3000));
        }
    }

    throw new ApiError("The engine is not responding. Try again in a minute.");
}

/** Purpose: Ask the backend for Mercuria's move and play it. */
async function requestBotMove() {
    const thinkMs = readThinkMs();
    try {
        await whileBusy("Mercuria is thinking…", async () => {
            const reply = await fetchBotMove(state.moves, thinkMs, readFeatureSwitches());
            state.moves.push(reply.move);
            showEngineReadout(reply);
            applyPosition(reply.position);
        });
    } catch (error) {
        showError(error, requestBotMove);
    }
}

/** Purpose: Start a fresh game. If the player chose Black, the engine moves first. */
async function startNewGame() {
    state.moves = [];
    state.playerColor = playerColorSelect.value;
    state.lastMove = [];
    state.pendingPromotion = null;

    try {
        await whileBusy("Setting up the board…", async () => {
            await waitForBackend();
            applyPosition(await fetchPosition([]));
        });
    } catch (error) {
        showError(error, startNewGame);
        return;
    }

    if (!isPlayersTurn()) {
        await requestBotMove();
    }
}

/** Purpose: Play the player's move, then let the engine answer. */
async function playPlayerMove(uci) {
    state.moves.push(uci);
    state.selected = null;
    state.pendingPromotion = null;
    try {
        await whileBusy("Checking your move…", async () => {
        applyPosition(await fetchPosition(state.moves));
        });
    } catch (error) {
        state.moves.pop(); // the move never reached the engine, so forget it
        renderAll();
        showError(error, renderAll);
        return;
    }
    if (state.position.status === "ongoing" && !isPlayersTurn()) {
        await requestBotMove();
    }
}

//  Reacting to clicks

/** Purpose: Called by board.js whenever a square is clicked. */
function handleSquareClick(square) {
    if (state.busy || !isPlayersTurn() || state.pendingPromotion) {
        return;
    }

    //  Second click: move the selected piece here, if that is legal.
    if (state.selected && currentTargets().includes(square)) {
        const options = state.legalByFrom[state.selected].filter((move) => move.slice(2, 4) === square);

        if (options.length > 1) {
            //  Several legal moves share these squares: it is a promotion. Ask which piece.
            state.pendingPromotion = [state.selected, square];
            renderAll();
        } else {
            playPlayerMove(options[0]);
        }

        return;
    }

    //  First click: select one of the player's own pieces that can move.
    const piece = state.pieces[square];
    const ownPiece = piece && piece[0] === state.playerColor;
    state.selected = ownPiece && state.legalByFrom[square] && state.selected !== square ? square : null;
    renderAll();
}

/** Purpose: The player picked a promotion piece. */
function handlePromotionChoice(pieceLetter) {
    if (!state.pendingPromotion) {
        return;
    }

    const [from, to] = state.pendingPromotion;
    playPlayerMove(from + to + pieceLetter);
}

//  Board style picker

const STYLE_STORAGE_KEY = "mercuria-board-style";

/** Purpose: Fill the "Board style" menu, restore the player's last choice, and apply it. */
function setUpBoardStyleChooser() {
    const select = $("board-style");
    for (const style of BOARD_STYLES) {
        const option = document.createElement("option");
        option.value = style.id;
        option.textContent = style.label;
        select.appendChild(option);
    }

    let saved = "mercury";
    try {
        saved = window.localStorage.getItem(STYLE_STORAGE_KEY) || saved;
    } catch (error) {
        //  Some browsers block storage (for example in private mode).
    }
    if (!BOARD_STYLES.some((style) => style.id === saved)) {
        saved = "mercury";
    }
    select.value = saved;
    applyBoardStyle(boardElement, saved);

    select.addEventListener("change", () => {
        applyBoardStyle(boardElement, select.value);
        try {
            window.localStorage.setItem(STYLE_STORAGE_KEY, select.value);
        } catch (error) {
        // Not saving the choice is harmless.
        }
    });
}

//  Wire up the page

setUpBoardStyleChooser();
newGameButton.addEventListener("click", startNewGame);
playerColorSelect.addEventListener("change", startNewGame);

$("think-time").addEventListener("change", readThinkMs);
promotionEl.querySelectorAll("button[data-piece]").forEach((button) => {
    button.addEventListener("click", () => handlePromotionChoice(button.dataset.piece));
});

$("promotion-cancel").addEventListener("click", () => {
    state.pendingPromotion = null;
    renderAll();
});

startNewGame();