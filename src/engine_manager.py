"""UCI engine management."""

import chess
import chess.engine
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from config import Priority


# Priority mappings for Windows
PRIORITY_MAP = {
    Priority.LOW: 'idle',
    Priority.BELOW_NORMAL: 'below_normal',
    Priority.NORMAL: 'normal',
}


@dataclass
class AnalysisResult:
    """Result from engine analysis."""
    
    move: chess.Move
    pv: List[chess.Move]  # Principal variation
    score_cp: Optional[int]  # Centipawns (None if mate)
    score_mate: Optional[int]  # Mate in N (None if not mate)
    depth: int = 0
    
    @property
    def is_mate(self) -> bool:
        return self.score_mate is not None
    
    def score_display(self) -> str:
        """Human-readable score."""
        if self.score_mate is not None:
            return f"M{self.score_mate}"
        elif self.score_cp is not None:
            return f"{self.score_cp / 100:+.2f}"
        return "?"
    
    def pv_san(self, board: chess.Board, max_moves: int = 5) -> str:
        """Return PV as SAN string."""
        pv_board = board.copy()
        san_moves = []
        for i, move in enumerate(self.pv[:max_moves]):
            if move in pv_board.legal_moves:
                san_moves.append(pv_board.san(move))
                pv_board.push(move)
            else:
                break
        return " ".join(san_moves)


class EngineManager:
    """Manages UCI engine lifecycle and analysis."""
    
    def __init__(self):
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.engine_path: Optional[Path] = None
        self.engine_name: str = "Unknown Engine"
        self.uci_options: Dict[str, Any] = {}
        self._process = None
    
    def load(self, path: Path, uci_options: Dict[str, Any] = None, priority: Priority = Priority.BELOW_NORMAL) -> bool:
        """
        Load engine from path.
        
        Args:
            path: Path to engine executable
            uci_options: UCI options to configure
            priority: Process priority level
            
        Returns:
            True if successful
        """
        self.close()
        
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(str(path))
            self.engine_path = path
            self.engine_name = self.engine.id.get("name", path.stem)
            
            # Get underlying process for priority setting
            if hasattr(self.engine, 'transport') and hasattr(self.engine.transport, 'get_pid'):
                pid = self.engine.transport.get_pid()
                self._set_priority(pid, priority)
            
            # Apply UCI options
            if uci_options:
                self.uci_options = uci_options
                self._apply_options(uci_options)
            
            return True
        except Exception as e:
            self.engine = None
            self.engine_path = None
            raise RuntimeError(f"Failed to load engine: {e}")
    
    def _set_priority(self, pid: int, priority: Priority) -> None:
        """Set process priority."""
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            proc = psutil.Process(pid)
            priority_name = PRIORITY_MAP.get(priority, 'below_normal')
            
            if hasattr(psutil, 'IDLE_PRIORITY_CLASS'):
                # Windows
                priority_classes = {
                    'idle': psutil.IDLE_PRIORITY_CLASS,
                    'below_normal': psutil.BELOW_NORMAL_PRIORITY_CLASS,
                    'normal': psutil.NORMAL_PRIORITY_CLASS,
                }
                proc.nice(priority_classes.get(priority_name, psutil.BELOW_NORMAL_PRIORITY_CLASS))
            else:
                # Unix - use nice values
                nice_values = {
                    'idle': 19,
                    'below_normal': 10,
                    'normal': 0,
                }
                proc.nice(nice_values.get(priority_name, 10))
        except Exception:
            pass  # Fail silently if unable to set priority
    
    def _apply_options(self, options: Dict[str, Any]) -> None:
        """Apply UCI options to engine."""
        if not self.engine:
            return
        
        for name, value in options.items():
            try:
                self.engine.configure({name: value})
            except Exception:
                # Skip invalid options silently
                pass
    
    def close(self) -> None:
        """Close engine if running."""
        if self.engine:
            try:
                self.engine.quit()
            except:
                pass
            self.engine = None
    
    def is_loaded(self) -> bool:
        """Check if engine is ready."""
        return self.engine is not None
    
    def analyze(
        self,
        board: chess.Board,
        depth_limit: int = 0,
        time_limit: float = 0.0,
        multipv: int = 1
    ) -> List[AnalysisResult]:
        """
        Analyze position and return candidate moves.
        
        Uses hybrid limit - stops when EITHER depth or time is reached.
        
        Args:
            board: Position to analyze
            depth_limit: Maximum depth (0 = no limit)
            time_limit: Maximum seconds (0 = no limit)
            multipv: Number of lines to return
            
        Returns:
            List of AnalysisResult, best first
        """
        if not self.engine:
            raise RuntimeError("Engine not loaded")
        
        # Build limit - hybrid mode (whichever comes first)
        limit_kwargs = {}
        if depth_limit > 0:
            limit_kwargs['depth'] = depth_limit
        if time_limit > 0:
            limit_kwargs['time'] = time_limit
        
        # Fallback if neither set
        if not limit_kwargs:
            limit_kwargs['depth'] = 16
        
        limit = chess.engine.Limit(**limit_kwargs)
        
        results = []
        
        try:
            infos = self.engine.analyse(
                board,
                limit,
                multipv=multipv
            )
            
            # Handle both single and multi-PV results
            if not isinstance(infos, list):
                infos = [infos]
            
            for info in infos:
                pv = info.get("pv", [])
                if not pv:
                    continue
                
                score = info.get("score")
                score_cp = None
                score_mate = None
                
                if score:
                    # Get score from perspective of side to move
                    pov_score = score.relative
                    if pov_score.is_mate():
                        score_mate = pov_score.mate()
                    else:
                        score_cp = pov_score.score()
                
                depth = info.get("depth", 0)
                
                results.append(AnalysisResult(
                    move=pv[0],
                    pv=pv,
                    score_cp=score_cp,
                    score_mate=score_mate,
                    depth=depth
                ))
        
        except chess.engine.EngineTerminatedError:
            raise RuntimeError("Engine terminated unexpectedly")
        
        return results
    
    def get_best_move(self, board: chess.Board, depth_limit: int = 0, time_limit: float = 0.0) -> Optional[chess.Move]:
        """
        Get single best move (faster than full analysis).
        
        Args:
            board: Position to analyze
            depth_limit: Maximum depth (0 = no limit)
            time_limit: Maximum seconds (0 = no limit)
            
        Returns:
            Best move or None
        """
        if not self.engine:
            return None
        
        # Build limit
        limit_kwargs = {}
        if depth_limit > 0:
            limit_kwargs['depth'] = depth_limit
        if time_limit > 0:
            limit_kwargs['time'] = time_limit
        if not limit_kwargs:
            limit_kwargs['depth'] = 16
        
        try:
            result = self.engine.play(board, chess.engine.Limit(**limit_kwargs))
            return result.move
        except:
            return None
    
    def get_config_summary(self) -> str:
        """Return summary of engine configuration."""
        parts = [self.engine_name]
        if 'Hash' in self.uci_options:
            parts.append(f"Hash={self.uci_options['Hash']}MB")
        if 'Threads' in self.uci_options:
            parts.append(f"Threads={self.uci_options['Threads']}")
        return " | ".join(parts)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False