/// Purpose: Renders the chessboard, displays pieces, and handles square interactions
///          This file only draws the board and reports clicks. It knows nothing about
///          chess rules. The backend decides which moves are legal, and main.js tells
///          this file what to highlight.

const FILES = "abcdefgh";

// The piece pictures. Files are named like w-king.png and b-pawn.png, and are
// copied here by tools/prepare_assets.py.
const PIECE_IMAGE_FOLDER = "assets/pieces";
const PIECE_NAMES = { K: "king", Q: "queen", R: "rook", B: "bishop", N: "knight", P: "pawn" };

/**
 *  Purpose: The board looks the player can pick.
 */
export const BOARD_STYLES = [
    { id: "mercury", label: "Mercury (plain)" },
    { id: "minimalist", label: "Minimalist" },
    { id: "choco", label: "Chocolate" },
    { id: "norse", label: "Norse wood" },
    { id: "sahara", label: "Sahara sand" },
    { id: "terra", label: "Terra grass and soil" },
    { id: "zora", label: "Zora marble" },
    { id: "elsa", label: "Elsa ice" },
    { id: "goron", label: "Goron rock" },
    { id: "cheron", label: "Cheron stone" },
];

/**
 *  Purpose: Read the piece positions out of a FEN string.
 *
 *  FEN lists the board rank by rank from rank 8 down to rank 1. Digits mean
 *  that many empty squares. Letters are pieces (capital = white).
 *
 *  @param {string} fen - Position text from the backend.
 *  @returns {Object<string, string>} Map from square name to piece code.
 *   Example: { e1: "wK", e8: "bK", a2: "wP" }
 */
export function parsePieces(fen) {
    const pieces = {};
    const rows = fen.split(" ")[0].split("/");

    rows.forEach((row, rowIndex) => {
        const rank = 8 - rowIndex;
        let fileIndex = 0;

        for (const char of row) {
            if (char >= "1" && char <= "8") {
                fileIndex += Number(char); // skip empty squares
            } else {
                const color = char === char.toUpperCase() ? "w" : "b";
                pieces[FILES[fileIndex] + rank] = color + char.toUpperCase();
                fileIndex += 1;
            }
        }
    });

    return pieces;
}

/**
 *  Purpose: List all 64 square names in the order they appear on screen, top-left first.
 *
 *  @param {"w"|"b"} orientation - "w" puts White at the bottom, "b" puts Black there.
 *  @returns {string[]} Square names such as ["a8", "b8", ..., "h1"].
 */
function squaresInDisplayOrder(orientation) {
    const ranks = orientation === "w" ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
    const files = orientation === "w" ? [...FILES] : [...FILES].reverse();
    const names = [];
    for (const rank of ranks) {
        for (const file of files) {
        names.push(file + rank);
        }
    }
    return names;
}

/** Purpose: A square is dark when its file number (a = 0) plus its rank number is odd. a1 is dark. */
function isDarkSquare(name) {
    return (FILES.indexOf(name[0]) + Number(name[1])) % 2 === 1;
}

/** Purpose: Describe a square for screen readers, such as "e4, white pawn" or "e5, empty". */
function describeSquare(name, pieceCode) {
    if (!pieceCode) {
        return `${name}, empty`;
    }

    const color = pieceCode[0] === "w" ? "white" : "black";
    return `${name}, ${color} ${PIECE_NAMES[pieceCode[1]]}`;
}

/** Purpose: Build the element that shows one piece, such as the picture of a white king. */
function createPieceElement(pieceCode) {
    const color = pieceCode[0];
    const element = document.createElement("span");
    element.className = `piece ${color === "w" ? "piece-white" : "piece-black"}`;

    const image = document.createElement("img");
    image.src = `${PIECE_IMAGE_FOLDER}/${color}-${PIECE_NAMES[pieceCode[1]]}.png`;
    image.alt = ""; // the square's button already has a spoken label
    image.draggable = false;
    element.appendChild(image);
    return element;
}

/**
 *  Purpose: Change how the board looks. Textures are applied with CSS variables.
 *          e.g. style.css reads --tile-light and --tile-dark as the background of the
 *          light and dark squares.
 *
 *  @param {HTMLElement} boardElement - The board.
 *  @param {string} styleId - An id from BOARD_STYLES.
 */
export function applyBoardStyle(boardElement, styleId) {
    if (styleId === "mercury") {
        delete boardElement.dataset.style;
        boardElement.style.removeProperty("--tile-light");
        boardElement.style.removeProperty("--tile-dark");
        return;
    }

    boardElement.dataset.style = styleId;
    boardElement.style.setProperty("--tile-light", `url("assets/boards/${styleId}/light.png")`);
    boardElement.style.setProperty("--tile-dark", `url("assets/boards/${styleId}/dark.png")`);
}

/**
 *  Purpose: Create the 64 clickable squares inside a container and return a view object.
 *
 *  @param {HTMLElement} boardElement - The empty element to fill.
 *  @param {(square: string) => void} onSquareClick - Called with a square name like "e4".
 *  @returns {{render: Function}} An object whose render() redraws the board.
 */
export function createBoardView(boardElement, onSquareClick) {
    const buttons = {}; // square name -> its <button>
    let currentOrientation = null;
    let keyboardSquare = "e2"; // the one square the Tab key lands on

    // Build each square once. Later redraws only change their contents.
    for (const name of squaresInDisplayOrder("w")) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `square ${isDarkSquare(name) ? "dark" : "light"}`;
        button.dataset.square = name;
        button.tabIndex = -1;
        buttons[name] = button;
    }

    /** Purpose: Put the buttons in the board in the right order for the chosen side. */
    function arrange(orientation) {
        const order = squaresInDisplayOrder(orientation);
        order.forEach((name, index) => {
        const row = Math.floor(index / 8);
        const column = index % 8;
        const button = buttons[name];
        boardElement.appendChild(button);

        // Small labels: file letters along the bottom row, rank numbers down the left column.
        button.querySelectorAll(".coord").forEach((label) => label.remove());
        if (row === 7) {
            button.appendChild(createCoordinate(name[0], "coord-file"));
        }

        if (column === 0) {
            button.appendChild(createCoordinate(name[1], "coord-rank"));
        }
        });

        boardElement.dataset.orientation = orientation;
        currentOrientation = orientation;
    }

    function createCoordinate(text, className) {
        const label = document.createElement("span");
        label.className = `coord ${className}`;
        label.textContent = text;
        label.setAttribute("aria-hidden", "true");
        return label;
    }

    /** Purpose: Make exactly one square reachable with the Tab key (arrow keys move between squares). */
    function setKeyboardSquare(name) {
        buttons[keyboardSquare].tabIndex = -1;
        keyboardSquare = name;
        buttons[keyboardSquare].tabIndex = 0;
    }

    boardElement.addEventListener("click", (event) => {
        const button = event.target.closest("button.square");

        if (button) {
            setKeyboardSquare(button.dataset.square);
            onSquareClick(button.dataset.square);
        }
    });

    // Arrow keys move the focus around the board.
    boardElement.addEventListener("keydown", (event) => {
        const steps = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
        const step = steps[event.key];
        if (!step) {
            return;
        }

        const order = squaresInDisplayOrder(currentOrientation);
        const index = order.indexOf(document.activeElement.dataset.square);
        const row = Math.floor(index / 8) + step[1];
        const column = (index % 8) + step[0];

        if (index >= 0 && row >= 0 && row < 8 && column >= 0 && column < 8) {
            event.preventDefault();
            setKeyboardSquare(order[row * 8 + column]);
            buttons[keyboardSquare].focus();
        }
    });

    /**
     *  Purpose: Redraw the whole board.
     *
     *  @param {object} view
     *  @param {Object<string,string>} view.pieces - Square name -> piece code, from parsePieces().
     *  @param {"w"|"b"} view.orientation - Which side is at the bottom.
     *  @param {string|null} view.selected - The selected square, if any.
     *  @param {string[]} view.targets - Squares the selected piece can move to.
     *  @param {string[]} view.lastMove - [from, to] of the previous move, or [].
     *  @param {string|null} view.checkSquare - Square of a king in check, if any.
     */
    function render({ pieces, orientation, selected, targets, lastMove, checkSquare }) {
        if (orientation !== currentOrientation) {
            arrange(orientation);
            setKeyboardSquare(keyboardSquare);
        }

        for (const [name, button] of Object.entries(buttons)) {
            const pieceCode = pieces[name] || null;

            // Replace the piece drawing only when it changed.
            if (button.dataset.piece !== (pieceCode || "")) {
                button.querySelectorAll(".piece").forEach((element) => element.remove());

                if (pieceCode) {
                    button.prepend(createPieceElement(pieceCode));
                }

                button.dataset.piece = pieceCode || "";
            }

            button.setAttribute("aria-label", describeSquare(name, pieceCode));
            button.classList.toggle("is-selected", name === selected);
            button.classList.toggle("is-target", targets.includes(name));
            button.classList.toggle("has-piece", pieceCode !== null);
            button.classList.toggle("is-last", lastMove.includes(name));
            button.classList.toggle("is-check", name === checkSquare);
        }
    }

    return { render };
}