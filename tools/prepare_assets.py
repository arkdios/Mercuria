# Purpose: Copy the chess pieces and board textures from the ChessCraft asset pack into frontend/assets
"""
Pieces are NOT changed. Board textures are shrunk from 512 to 160 pixels,
because the originals are about 0.5 MB each and a page should load fast. That
is a change to the artwork, so it is listed in frontend/assets/CREDITS.md.
"""

import argparse
import shutil
from pathlib import Path

from PIL import Image

DEFAULT_SOURCE = "chesscraft-creative-commons-master/assets"
DESTINATION = Path("frontend/assets")

PIECE_FOLDER = "Resources/Pieces/01_classic"
PIECE_COLORS = ("w", "b")
PIECE_NAMES = ("king", "queen", "rook", "bishop", "knight", "pawn")

# Every board style in the pack. Each has four tiles: wa and ba are the normal light and dark squares.
# wi and bi are dimmed copies the original game uses for blocked squares, which this website does not need.
BOARD_STYLES = ("minimalist", "choco", "norse", "sahara", "terra", "zora", "elsa", "goron", "cheron")
TILE_SIZE = 160 # In pixels. Squares are about 80 px wide, so this stays sharp on high-resolution screens.

# Purpose: Copy the 12 piece images unchanged. Returns how many were copied.
def copy_pieces(source: Path) -> int:
    target = DESTINATION / "pieces"
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for color in PIECE_COLORS:
        for name in PIECE_NAMES:
            file_name = f"{color}-{name}.png"
            shutil.copyfile(source / PIECE_FOLDER / file_name, target / file_name)
            count += 1
    return count

# Purpose: Shrink each style's light and dark tile and save them as light.png and dark.png.
def make_board_tiles(source: Path) -> int:
    count = 0
    for style in BOARD_STYLES:
        target = DESTINATION / "boards" / style
        target.mkdir(parents=True, exist_ok=True)
        for tile_name, output_name in (("wa", "light"), ("ba", "dark")):
            tile = Image.open(source / "Sprites/board/themes" / style / f"{style}-{tile_name}.png")
            tile.convert("RGB").resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS).save(
                target / f"{output_name}.png", optimize=True
            )
            count += 1
    return count

# Purpose: Read the command line, run both steps, and copy the license.
def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare website images from the ChessCraft asset pack.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="the pack's assets folder")
    args = parser.parse_args()

    source = Path(args.source)
    if not (source / PIECE_FOLDER).is_dir():
        raise SystemExit(f"Cannot find {source / PIECE_FOLDER}. Pass the pack's assets folder with --source.")

    pieces = copy_pieces(source)
    tiles = make_board_tiles(source)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source.parent / "LICENSE", DESTINATION / "LICENSE-CC-BY-SA-4.0.txt")
    print(f"Copied {pieces} pieces and made {tiles} board tiles in {DESTINATION}/")


if __name__ == "__main__":
    main()