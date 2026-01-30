"""PGN writer with RAV (variation) support."""

from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
import chess
import chess.pgn


@dataclass
class AnalyzedGame:
    """Container for a game with analyzed variations."""
    
    root_game: chess.pgn.Game = field(default_factory=chess.pgn.Game)
    
    def set_headers(
        self,
        event: str = "Interval Analysis",
        site: str = "Localhost",
        date: str = "????.??.??",
        round_: str = "-",
        white: str = "Engine",
        black: str = "Repertoire",
        result: str = "*"
    ) -> None:
        """Set all required PGN headers."""
        self.root_game.headers["Event"] = event
        self.root_game.headers["Site"] = site
        self.root_game.headers["Date"] = date
        self.root_game.headers["Round"] = round_
        self.root_game.headers["White"] = white
        self.root_game.headers["Black"] = black
        self.root_game.headers["Result"] = result


class PGNWriter:
    """Writes PGN files with proper headers and RAV support."""
    
    def __init__(self, base_path: Path, split_size_mb: int = 10):
        """
        Initialize PGN writer.
        
        Args:
            base_path: Base output path (e.g., output.pgn)
            split_size_mb: Split into new file after this size
        """
        self.base_path = base_path
        self.split_size_bytes = split_size_mb * 1024 * 1024
        self.current_file_index = 0
        self.current_size = 0
        self.games_written = 0
        self._current_path: Optional[Path] = None
    
    def _get_current_path(self) -> Path:
        """Get current output file path, handling splits."""
        if self.current_file_index == 0:
            return self.base_path
        else:
            stem = self.base_path.stem
            suffix = self.base_path.suffix
            return self.base_path.parent / f"{stem}_{self.current_file_index}{suffix}"
    
    def _check_split(self) -> None:
        """Check if we need to start a new file."""
        current_path = self._get_current_path()
        if current_path.exists():
            self.current_size = current_path.stat().st_size
            if self.current_size >= self.split_size_bytes:
                self.current_file_index += 1
                self.current_size = 0
    
    def write_game(self, game: chess.pgn.Game) -> Path:
        """
        Write a game to the current PGN file.
        
        Args:
            game: Game object with headers and moves
            
        Returns:
            Path to file where game was written
        """
        self._check_split()
        current_path = self._get_current_path()
        
        # Ensure directory exists
        current_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Format game as string
        exporter = chess.pgn.StringExporter(
            headers=True,
            variations=True,
            comments=True
        )
        pgn_string = game.accept(exporter)
        
        # Ensure proper termination
        result = game.headers.get("Result", "*")
        if not pgn_string.rstrip().endswith(result):
            pgn_string = pgn_string.rstrip() + " " + result
        
        # Append to file
        with open(current_path, 'a', encoding='utf-8') as f:
            f.write(pgn_string)
            f.write("\n\n")
        
        self.games_written += 1
        self._current_path = current_path
        
        return current_path
    
    def create_game(
        self,
        engine_name: str = "Stockfish",
        perspective: str = "White",
        config_summary: str = ""
    ) -> chess.pgn.Game:
        """
        Create a new game with proper headers.
        
        Args:
            engine_name: Name of analysis engine
            perspective: 'White' or 'Black' repertoire
            config_summary: Brief config description for Black header
            
        Returns:
            New game object ready for moves
        """
        game = chess.pgn.Game()
        
        game.headers["Event"] = "Interval Analysis"
        game.headers["Site"] = "Localhost"
        game.headers["Date"] = "????.??.??"
        game.headers["Round"] = "-"
        game.headers["White"] = engine_name
        game.headers["Black"] = f"{perspective} Repertoire{' - ' + config_summary if config_summary else ''}"
        game.headers["Result"] = "*"
        
        return game
    
    def get_files_written(self) -> List[Path]:
        """Return list of all files written."""
        files = []
        for i in range(self.current_file_index + 1):
            if i == 0:
                path = self.base_path
            else:
                stem = self.base_path.stem
                suffix = self.base_path.suffix
                path = self.base_path.parent / f"{stem}_{i}{suffix}"
            if path.exists():
                files.append(path)
        return files
    
    @property
    def last_written_path(self) -> Optional[Path]:
        """Return the most recently written file path."""
        return self._current_path
    
    @staticmethod
    def merge_files(input_paths: List[Path], output_path: Path) -> int:
        """
        Merge multiple PGN files into one.
        
        Args:
            input_paths: List of input PGN file paths
            output_path: Output merged PGN file path
            
        Returns:
            Number of games written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        games_written = 0
        
        with open(output_path, 'w', encoding='utf-8') as out_f:
            for input_path in input_paths:
                if not input_path.exists():
                    continue
                
                try:
                    with open(input_path, 'r', encoding='utf-8', errors='replace') as in_f:
                        content = in_f.read()
                        if content.strip():
                            out_f.write(content)
                            if not content.endswith('\n\n'):
                                out_f.write('\n\n')
                            # Rough count of games
                            games_written += content.count('[Event ')
                except Exception:
                    continue
        
        return games_written