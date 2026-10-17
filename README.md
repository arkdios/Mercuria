# Mercuria  
Mercuria is a chess bot you play against in your browser. The engine is written in Python. The website is plain HTML, CSS, and JavaScript.  
   
## Status  
   
Planning Stage  
  
## Tech stack  
  
| Part | Technology |  
| --- | --- |  
| Frontend | HTML, CSS, JavaScript |  
| Backend | Python |  
| Frontend hosting | GitHub Pages |  

## How it works  
   
1. The player moves a piece on the board.  
2. The frontend sends the game state to the backend through its API.  
3. The backend searches for the best reply.  
4. The reply goes back to the browser and the board updates.  
   
## Project structure  
   
```
Mercuria/
├── backend/
│   ├── app.py
│   ├── board.py
│   ├── config.py
│   ├── engine.py
│   ├── evaluation.py
│   ├── move_ordering.py
│   ├── movegen.py
│   ├── search.py
│   ├── transposition_table.py
│   └── zobrist.py
├── frontend/
│   ├── api.js
│   ├── board.js
│   ├── index.html
│   ├── main.js
│   └── style.css
└── README.md
```  
  
## Credits  
   
Chess pieces, the board, and some UI elements are free assets from the web.  