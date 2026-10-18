/// Purpose: Handles communication with the Python backend

const LOCAL_API_URL = "http://127.0.0.1:5000";
/// const HOSTED_API_URL = "https://backend-name.onrender.com"; // TODO: replace after deploying

const runsLocally = ["localhost", "127.0.0.1"].includes(window.location.hostname);
export const API_BASE_URL = runsLocally ? LOCAL_API_URL : HOSTED_API_URL;

/** An error whose message is safe to show to the player. */
export class ApiError extends Error {}

/**
 * Purpose: Send one request to the backend and return its JSON answer.
 *
 * @param {string} path - Address on the backend, such as "/api/position".
 * @param {object} [options]
 * @param {object} [options.body] - Data to send. If given, the request is a POST.
 * @param {number} [options.timeoutMs] - Give up after this many milliseconds.
 * @returns {Promise<object>} The parsed JSON answer.
 * @throws {ApiError} If the server cannot be reached or reports a problem.
 */
async function request(path, { body, timeoutMs = 15000 } = {}) {
    // AbortController lets us cancel a request that takes too long.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(API_BASE_URL + path, {
            method: body ? "POST" : "GET",
            headers: body ? { "Content-Type": "application/json" } : {},
            body: body ? JSON.stringify(body) : undefined,
            signal: controller.signal,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new ApiError(data.error || "The engine rejected that request.");
        }
        return data;
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }

        if (error.name === "AbortError") {
            throw new ApiError("The engine took too long to answer.");
        }

        throw new ApiError("Cannot reach the engine. Check your connection and try again.");
    } finally {
        clearTimeout(timer);
    }
}

/** Purpose: Ask the backend if it is awake. Free hosts sleep when idle, so this can be slow. */
export function ping() {
    return request("/health", { timeoutMs: 10000 });
}

/**
 * Purpose: Get the position reached after a list of moves.
 *
 * @param {string[]} moves - Moves played so far, such as ["e2e4", "e7e5"].
 * @returns {Promise<object>} fen, turn, legal_moves, in_check, check_square, status, winner.
 */
export function fetchPosition(moves) {
    return request("/api/position", { body: { moves } });
}

/**
 * Purpose: Ask the engine for its move.
 *
 * @param {string[]} moves - Moves played so far.
 * @param {number} thinkMs - How long the engine may think, in milliseconds.
 * @param {object} features - On/off switches: alpha_beta, move_ordering, transposition_table.
 * @returns {Promise<object>} move, score, depth, nodes, time_ms, and the new position.
 */
export function fetchBotMove(moves, thinkMs, features) {
    // Allow extra time for the network on top of the engine's thinking time.
    return request("/api/bot-move", {
        body: { moves, think_ms: thinkMs, features },
        timeoutMs: thinkMs + 15000,
    });
}