# Tidypy Chess Interval Analyzer

Portable desktop tool for creating engine-verified chess repertoires using **Interval Analysis**.

LESS COMMONLY KNOWN AS:  **Tabiyas (pronounced Tah-bee-yuhs) Tables.**
It is a specific term from the Arabic roots of chess (Shatranj) that has survived into modern engine programming.

Definition: A standard, well-known position in the opening from which the "real game" begins.

In your tool: you set increments that iterate throughout the PGN and jump to Move 7, Move 14, etc., it is essentially creating a series of Tabiyas—critical positions where the players have finished a sequence of moves and must now make a strategic decision.

The Math: uses Zobrist Hashing. 
Why it feels like "Intervals": The engine creates a map of these hashes. If your PGN loops back to a position it saw 5 moves ago (a transposition), the "Matrix" instantly recognizes it via the Zobrist key. A unique workaround for EPD injection/conversion requirements.

## 🎯 The Problem
Traditional chess analysis tools are inefficient for repertoire building. They either:
1.  **Analyze every move:** Wasting hours on obvious moves.
2.  **Analyze only the end:** Missing the critical turning points in the opening/middlegame transition.
3.  **Dependency Hell:** Require complex Python environments that break easily on different machines.

## 💡 The Solution: Interval Analysis
This tool does not perform an autopsy on a "dead" game. Instead, it takes **Biopsies** at specific intervals.

It scans a PGN file, jumps to **Move 7** for example, analyzes the position, grafts the best engine line according to Your engine and parameters onto the game, then jumps to **Move 14**, and repeats. This creates a high-quality "Skeleton Repertoire" that overwrites engine truth, while preserving the original game context for tools like Lucas Chess.
**In Short**, you can set the engine to perform the way you want, Run it through games and create a Reperitoir the is UNIQUE to the playstyle you desire. 

## ✨ Key Features

### 🛡️ Robust Engine Architecture
* **Handshake Protocol:** Automatically "pings" engines on load. If an engine doesn't reply in 5 seconds (TTL), it is safely terminated.
* **Crash Protection:** Detects "Illegal Instruction" errors (e.g., trying to run AVX2 engines on older CPUs) and warns the user instead of silently crashing.
* **Dynamic Configuration:** Reads your engine's specific capabilities (NNUE, Hash, Threads) and generates a settings menu on the fly.

### 🧠 Smart "Biopsy" Workflow
* **Interval Logic:** Set an increment (e.g., every 7 moves) to focus only on critical tabiyas.
* **Perspective Aware:** Automatically handles ply conversions for White vs. Black repertoires.
* **Live Matrix Feed:** Streams UCI data (Depth, Score, PV) in real-time.
* **Smart Throttling:** Logs are updated intelligently to keep the UI responsive, even with high-nodes-per-second engines.

### 📦 "Zero-Dependency" Portable App
* Built with `PyInstaller` and `PyQt6`.
* Runs as a standalone folder on Windows/Linux.
* No Python installation required for end-users.

---

## 🚀 Quick Start (Portable Mode)

1.  **Download** the latest release from the [Releases Page](../../releases).
2.  **Unzip** the folder.
3.  **Run** `ChessIntervalAnalyzer.exe` (Windows) or the binary (Linux).
4.  **Load Engine:** Select your UCI engine (Stockfish, Komodo, etc.).
5.  **Configure:** Click **Configure UCI** to tune Hash/Threads.
6.  **Set Intervals:**
    * *Skip First:* 0 (Start at the beginning)  -- will skip the first moves of the game, zero skips nothing, If you are a blitz player and often transpose using the same opening pattern, engines with NNUE or a baked in book will use their book and rewrite the variation accordingly. 
    * *Increment:* 7 (Analyze every 7 moves)  -- well iterate through the PGN, unlike ALL Book tools today, it does not require EPD Position injection, it will not truncate out of book play, or miss the out of book play later in the game. Example if you train on a created book, it is likely you will enter a sub-standard line or make a human decision, this tool will capture most candidate moves in your set tolarance and allow you to build a through book. Great for gambit lines or exclam moves that engines won't consider, like a fishhook sac or greek gift that may require OnlyMoves to refute.  
    * *Max Move:* 24 (Stop deep analysis after move 24)  -- Designed to limit the analysis by PLY, this tool is to create a reperitoire of not-so main line replies to pattern play. Other book tuning tools will not capture then overwrite the mainline with a variation of lesser truth. 
7.  **Run:** Click **Start Processing**.

---

## 🚀 Detailed Best Practices 

1.  **Utilize a chess GUI:** Utilize Lucas chess or SCID to create a PGN of filtered games for your book, This is your base. This eliminates the need to use book creation tools and have to Go to the engine folder and import the engines book.bin (which is actually just the authors tuning not really just the engines tuned replies, or it is the NNUE baked in responses which my tool will extract anyway.)
2.  **After running the Tidypy tool** Utilize a GUI like Lucas Chess to Import your newly created PGN, and create your opening book with GUI Tools in Lucas; the PGN Import suggested settings are **"Uniform Distribution, MAX PLY 60, MIN Games=1, Only white/black=UN-Checked"**.  Critical. This tidypy-tool generates specific candidate moves (e.g., 2 candidates). Since each appears only once in your PGN, "Uniform" ensures the engine picks any of them with equal probability. If you chose "Proportional," it wouldn't make sense because the sample size is 1. MIN Games 1, because each variation will be unique. Un-checked Only white/black, because this tool already does this as its required by my tool to create a proper Reperitoire. 
3.  **File Size:** Some OS versions and tools like Kate for linux have Character restraints on 'how big' a text file can be 64k characters for example. Also GUI import book tools break often if the PGN is larger then 24MB for example. Keep your file size small and tight, importing 5 times is better then troubleshooting 1 corrupt output file you spent hours computing. 
4.  **Candidate Moves:** Keep it to 1-2, 2 candidates slows the app down by 50%, 3 candidate moves exponentially increases file size and increase time to complete performance drops to %25.  Besides you want 1-2 candidates only as your UCI engine parameters are scanning for that, Engines have a Multi-PV even when selecting 1 candidate move.  My app uses logic to dictate what is a blunder, and what is mainline by comparing PV stdout of the engines centipawn evaluation. 4 candidate moves and you will be going on vacation.
5.  **MAX Line:**  set to 24, with analysis of engine tournament play, I have found most engines break at move 26-27, for many out of scope reasons, I choose NOT to create a Range, because this breaks most import PGN book tools as the lines are truncated. If you have a specific need for middlegame analysis please create an Issue request, we might do a fork build, this tool is not for position EPD analysis stockfish has that covered. I do wish Lichess would release their Dev Analysis options.  MAX 24 is the sweet spot for low RAM users, and fast iteration throught large PGN of games. 
6.  **Your Database:**  Lichess Elite Database by Nikonoe, Lumbra's Gigabase, Cassandra DB, OpeningTree.org, CCRL computer chess archive, FICS, Create an engine tournament, or Create one with Norman Polock Position Tool in Lucas Chess for example.
7.  **PGN Output Cleaning:** Some GUI have bugs, or just don't work as expected on import.  You may want to take the PGN outputs, and import them first creating a new Database, SCID prefers to convert the PGN before the GUI Book tool is run.  Other GUI tools want to convert/create a SQLite table first.  My output is ISO Standard, so Meh. BUT Most parsers are lazy and won't do more then one variation, or will settle on mainline only.  Luckily my tool overwrites mainline, so we capture most there.  TODO is create a .bin polyglot creation button to ensure full Uniform ingestion.    

---

## 🛠️ Developer Setup

If you wish to contribute or run from source:

### Prerequisites
* Python 3.10+
* Virtual Environment recommended

### Installation
```bash
# 1. Clone the repository
git clone [https://github.com/Tidypy/chess-interval-analyzer.git](https://github.com/Tidypy/chess-interval-analyzer.git)
cd chess-interval-analyzer

# 2. Create Virtual Environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install Dependencies
pip install -r requirements.txt
