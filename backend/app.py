# Purpose: Host the Python backend and expose the API for the JS frontend
import dataclasses
import os
import re

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from config import ALLOWED_ORIGINS, DEFAULT_THINK_MS, MAX_MOVES_PER_REQUEST
# from engine import Engine
from search import SearchOptions

app = Flask(__name__)
# engine = Engine()

# A UCI move: two squares, then an optional promotion letter.
_UCI_PATTERN = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")

# The engine speedups a request may switch on or off.
_FEATURE_NAMES = tuple(field.name for field in dataclasses.fields(SearchOptions))

# Cross-origin access
# Purpose: Let the frontend's origin call this API from the browser.
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")

    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Vary"] = "Origin"

    return response

# Input validation

class InvalidRequest(Exception):
    """A request the client got wrong."""

# Purpose: Return the request's JSON object, or raise InvalidRequest if it is missing or not an object.
def read_json_body() -> dict:
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        raise InvalidRequest("The request body must be a JSON object.")
    
    return body

# Validate the moves field and return it.
def read_moves(body: dict) -> list:
    moves = body.get("moves")

    if not isinstance(moves, list):
        raise InvalidRequest("'moves' must be a list of moves such as 'e2e4'.")
    
    if len(moves) > MAX_MOVES_PER_REQUEST:
        raise InvalidRequest(f"'moves' can hold at most {MAX_MOVES_PER_REQUEST} moves.")
    
    for text in moves:
        if not isinstance(text, str) or not _UCI_PATTERN.match(text):
            raise InvalidRequest("Every move must look like 'e2e4' or 'e7e8q'.")
        
    return moves

# Purpose: Validate the optional think_ms field, returning the default when it is absent.
def read_think_ms(body: dict) -> int:
    value = body.get("think_ms", DEFAULT_THINK_MS)

    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidRequest("'think_ms' must be a whole number of milliseconds.")
    
    return value

# Purpose: Validate the optional features field and build the search options.
def read_options(body: dict) -> SearchOptions:
    features = body.get("features", {})

    if not isinstance(features, dict):
        raise InvalidRequest("'features' must be an object of true/false switches.")
    
    for name, value in features.items():
        if name not in _FEATURE_NAMES or not isinstance(value, bool):
            raise InvalidRequest(f"'features' may only contain true/false for: {', '.join(_FEATURE_NAMES)}.")
        
    return SearchOptions(**features)

# Routes
# Purpose: Report that the server is up.
@app.get("/health")
def health():
    return jsonify({"status": "ok"})

"""
# Purpose: Describe the position reached by the given moves.
@app.post("/api/position")
def position():
    moves = read_moves(read_json_body())

    try:
        return jsonify(engine.position(moves))

    except ValueError as error:
        raise InvalidRequest(str(error)) from error

# Purpose: Choose and play the bot's move for the given game.
@app.post("/api/bot-move")
def bot_move():
    body = read_json_body()
    moves = read_moves(body)
    think_ms = read_think_ms(body)
    options = read_options(body)

    try:
        return jsonify(engine.bot_move(moves, think_ms, options))

    except ValueError as error:
        raise InvalidRequest(str(error)) from error
"""
# Error handling
# Purpose: Return a client mistake as JSON with status 400.
@app.errorhandler(InvalidRequest)
def handle_bad_request(error):
    return jsonify({"error": str(error)}), 400

# Purpose: Return Flask's own errors (404, 405, ...) as JSON instead of HTML.
@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code

# Purpose: Return a generic 500. Details go to the server log, never to the client.
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled error: %s", error)
    return jsonify({"error": "Something went wrong on the server."}), 500

if __name__ == "__main__":
    # Local development only. Production uses gunicorn (see the README).
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))