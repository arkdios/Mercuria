#!venv/bin/python3

"""
Use ChessCraft piece images to generate one big image with many.

Usage:
  generate-previews.py [options]

Options:
  --width=<pixels>      The width of the PNG. Height is calculated for a 1:1 aspect ratio. [default: 1024]
  --columns=<rows>      Column count. [default: 12]
  --rows=<rows>         Row count. [default: 6]
  --color-pairs         White and black versions of a piece are side by side, instead of all random.
  --blacklist=<b>       Comma delimited list of substrings. Exclude a PNG if it's full path contains any. [default: woodland,helios,berserker,zora]
  --output=<path>       Where to write the output file. [default: %s]
  
  -h --help           Show this screen.
  -v --version        Show version.
"""

import os.path
d=os.path.dirname
path=d(d(os.path.realpath(__file__)))+"/previews/pieces.png"
__doc__%=path

from docopt import docopt
import random
import os
from PIL import Image

def get_matching_paths_recursively(rootdir, extension, verbose=0):
    "Returns a list of full paths. Searches 'rootdir' recursively for all files with 'extension'."
    if verbose:
        print("Getting filenames for files with extension \"%s\" at:\n%s" %
              (extension, rootdir))
    results = []
    for root, _, filenames in os.walk(rootdir):
        for filename in filenames:
            if filename.find(extension) == len(filename) - len(extension):
                path = os.path.join(root, filename)
                results.append(path)
    return results

def filter_paths(paths, extra_blacklist=()):
    blacklist=("01_classic","06_classic2","07_berserker") + tuple(extra_blacklist)
    for black in blacklist:
        paths=[path for path in paths if black not in path]
    return paths

def get_pieces_dictionary(source_folder, extra_blacklist=()):
    "pieces = {'pawn.png' : ('path/w-pawn.png', 'path/b-pawn.png')}"
    
    paths=get_matching_paths_recursively(source_folder,".png")
    paths=filter_paths(paths, extra_blacklist)
    random.shuffle(paths)    
    pieces={}
    for path in paths:
        # trim "w-" or "b-"
        key=path.split(os.sep)[-1][2:]
        if key not in pieces:
            pieces[key]=["",""]
        
        if os.sep+"w-" in path:
            pieces[key][0]=path
        elif os.sep+"b-" in path:
            pieces[key][1]=path
        else:
            print(f"Ignored '{path}'. Expected a PNG starting with 'w-' or 'b-'.")
    return pieces

def generate_pieces_preview_image(output_path,width,height,column_count,row_count,color_pairs=True,extra_blacklist=()):
    source_folder="assets/Resources/Pieces"
    target_folder=os.path.dirname(output_path)
    cell_width=int(width/column_count)
    cell_height=int(height/row_count)

    tile_white=Image.open("assets/Sprites/board/themes/norse/norse-wa.png").convert("RGBA")
    tile_black=Image.open("assets/Sprites/board/themes/norse/norse-ba.png").convert("RGBA")
    tile_white=tile_white.resize((cell_width,cell_height),Image.Resampling.LANCZOS)    
    tile_black=tile_black.resize((cell_width,cell_height),Image.Resampling.LANCZOS)
    
    if not os.path.isdir(target_folder):
        os.mkdir(target_folder)
    
    preview_image=Image.new("RGBA",(width,height))
    
    piece_dictionary=get_pieces_dictionary(source_folder, extra_blacklist)

    """
    If the number of tiles is fewer than the number of pieces, we want to guarantee all unique pieces.
    Otherwise, we still want to guarantee an even spread with this append and shuffle.
    """
    piece_pairs=[]
    area=width*height
    while len(piece_pairs) < area:
        a=list(piece_dictionary.values())
        random.shuffle(a)
        piece_pairs+=a
    
    index=0                
    for j in range(row_count):
        for i in range(column_count):
            
            if color_pairs:
                if i%2==0:
                    index+=1
            else:
                index+=1
                
            chosen=piece_pairs[index][i%2]
            
            piece_image=Image.open(chosen).convert("RGBA")
            piece_image=piece_image.resize((cell_width,cell_height),Image.Resampling.LANCZOS)
            x=i*cell_width
            y=j*cell_height
            
            tile_image=tile_white if (i+j)%2==0 else tile_black
            preview_image.paste(tile_image,(x,y,x+cell_width,y+cell_height))
            
            preview_image.paste(piece_image,(x,y,x+cell_width,y+cell_height),piece_image)
            
    preview_image.save(output_path)
    print(__file__ + f" wrote new file: '{output_path}'")

def main(args):
    
    try:
        width=int(args["--width"])
        column_count=int(args["--columns"])
        row_count=int(args["--rows"])
    except:
        print("Bad width, columns, or rows.")
        return

    tile_width=int(width/column_count)
    height=tile_width*row_count
    
    blacklist_arg=args["--blacklist"]
    if blacklist_arg in (True,False):
        blacklist_arg=None
    extra_blacklist=blacklist_arg.split(",") if blacklist_arg else ()

    generate_pieces_preview_image(args["--output"],
                                  width,
                                  height,
                                  column_count,
                                  row_count,
                                  color_pairs=args["--color-pairs"],
                                  extra_blacklist=extra_blacklist)

if __name__ == "__main__":
    args = docopt(__doc__, version="1.0")
    main(args)

