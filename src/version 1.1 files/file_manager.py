"""File management utilities."""

from pathlib import Path
from typing import Optional, Iterator, List
import chess.pgn


class FileManager:
    """Handles input/output file operations."""
    
    @staticmethod
    def validate_input_pgn(path: Path) -> tuple[bool, str]:
        """
        Validate input PGN file.
        
        Returns:
            (is_valid, message)
        """
        if not path.exists():
            return False, f"File not found: {path}"
        
        if not path.is_file():
            return False, f"Not a file: {path}"
        
        if path.suffix.lower() != '.pgn':
            return False, f"Not a PGN file: {path}"
        
        # Try to read first game
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                game = chess.pgn.read_game(f)
                if game is None:
                    return False, "No valid games found in file"
        except Exception as e:
            return False, f"Error reading file: {e}"
        
        return True, "Valid PGN file"
    
    @staticmethod
    def count_games(path: Path) -> int:
        """Count number of games in PGN file."""
        count = 0
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                while chess.pgn.read_game(f) is not None:
                    count += 1
        except:
            pass
        return count
    
    @staticmethod
    def iterate_games(path: Path) -> Iterator[chess.pgn.Game]:
        """
        Iterate through games in PGN file.
        
        Yields:
            chess.pgn.Game objects
        """
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                yield game
    
    @staticmethod
    def iterate_games_with_index(path: Path) -> Iterator[tuple[int, chess.pgn.Game]]:
        """
        Iterate through games in PGN file with indices.
        
        Yields:
            (index, chess.pgn.Game) tuples
        """
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            index = 0
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                yield index, game
                index += 1
    
    @staticmethod
    def get_game_by_index(path: Path, target_index: int) -> Optional[chess.pgn.Game]:
        """
        Get a specific game by index.
        
        Args:
            path: PGN file path
            target_index: Zero-based game index
            
        Returns:
            Game at index or None
        """
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                for i in range(target_index + 1):
                    game = chess.pgn.read_game(f)
                    if game is None:
                        return None
                    if i == target_index:
                        return game
        except:
            pass
        return None
    
    @staticmethod
    def validate_engine(path: Path) -> tuple[bool, str]:
        """
        Validate engine executable.
        
        Returns:
            (is_valid, message)
        """
        if not path.exists():
            return False, f"Engine not found: {path}"
        
        if not path.is_file():
            return False, f"Not a file: {path}"
        
        # Check if executable (basic check)
        suffix = path.suffix.lower()
        if suffix not in ['.exe', '']:
            return False, f"Unexpected file type: {suffix}"
        
        return True, "Engine file exists"
    
    @staticmethod
    def generate_output_path(input_path: Path, suffix: str = "_analyzed") -> Path:
        """
        Generate output path based on input.
        
        Args:
            input_path: Input PGN path
            suffix: Suffix to add before extension
            
        Returns:
            New path for output
        """
        return input_path.parent / f"{input_path.stem}{suffix}.pgn"
    
    @staticmethod
    def generate_bin_path(input_path: Path, suffix: str = "_book") -> Path:
        """
        Generate Polyglot book path based on input.
        
        Args:
            input_path: Input PGN path
            suffix: Suffix to add before extension
            
        Returns:
            New path for .bin output
        """
        return input_path.parent / f"{input_path.stem}{suffix}.bin"
    
    @staticmethod
    def generate_temp_path(base_path: Path, worker_id: int, extension: str) -> Path:
        """
        Generate temporary file path for a worker.
        
        Args:
            base_path: Base output path
            worker_id: Worker identifier
            extension: File extension (e.g., '.pgn', '.bin')
            
        Returns:
            Temporary file path
        """
        return base_path.parent / f".tidypy_temp_w{worker_id}{extension}"
    
    @staticmethod
    def cleanup_temp_files(base_path: Path, num_workers: int) -> None:
        """
        Remove temporary worker files.
        
        Args:
            base_path: Base output path
            num_workers: Number of workers
        """
        for worker_id in range(num_workers):
            for ext in ['.pgn', '.bin']:
                temp_path = FileManager.generate_temp_path(base_path, worker_id, ext)
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except:
                    pass
    
    @staticmethod
    def ensure_directory(path: Path) -> None:
        """Ensure parent directory exists."""
        path.parent.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def distribute_games(total_games: int, num_workers: int) -> List[List[int]]:
        """
        Distribute game indices among workers.
        
        Uses round-robin distribution so each worker gets
        roughly equal number of games.
        
        Args:
            total_games: Total number of games
            num_workers: Number of workers
            
        Returns:
            List of game index lists, one per worker
            
        Example:
            distribute_games(10, 3) returns:
            [[0, 3, 6, 9], [1, 4, 7], [2, 5, 8]]
        """
        distribution = [[] for _ in range(num_workers)]
        
        for game_idx in range(total_games):
            worker_idx = game_idx % num_workers
            distribution[worker_idx].append(game_idx)
        
        return distribution