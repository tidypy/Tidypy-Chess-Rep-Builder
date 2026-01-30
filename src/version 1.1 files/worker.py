"""Analysis worker thread."""

from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
from typing import Optional, List, Set
import chess
import chess.pgn

from config import AnalysisConfig, Perspective, Priority
from ply_utils import generate_analysis_plies, format_ply_for_display, ply_to_move
from engine_manager import EngineManager, AnalysisResult
from pgn_writer import PGNWriter
from polyglot_writer import PolyglotWriter
from file_manager import FileManager


class AnalysisWorker(QThread):
    """Background worker for interval analysis."""
    
    # Signals
    progress = pyqtSignal(int, int, int)  # worker_id, current_game, total_games
    log_message = pyqtSignal(int, str)  # worker_id, message
    game_completed = pyqtSignal(int, str)  # worker_id, filename
    worker_finished = pyqtSignal(int, bool, str, int, int)  # worker_id, success, message, games, positions
    position_analyzed = pyqtSignal(int, str)  # worker_id, detailed analysis line
    
    def __init__(
        self,
        config: AnalysisConfig,
        worker_id: int,
        game_indices: List[int],
        uci_options: dict,
        priority: Priority,
        temp_pgn_path: Optional[Path] = None,
        temp_bin_path: Optional[Path] = None
    ):
        super().__init__()
        self.config = config
        self.worker_id = worker_id
        self.game_indices: Set[int] = set(game_indices)
        self.uci_options = uci_options
        self.priority = priority
        self.temp_pgn_path = temp_pgn_path
        self.temp_bin_path = temp_bin_path
        self._stop_requested = False
        self.engine: Optional[EngineManager] = None
    
    def request_stop(self) -> None:
        """Request graceful stop after current game."""
        self._stop_requested = True
        self._log(f"Stop requested - finishing current game...")
    
    def _log(self, message: str) -> None:
        """Emit log message with worker ID."""
        self.log_message.emit(self.worker_id, message)
    
    def run(self) -> None:
        """Main analysis loop."""
        try:
            self._run_analysis()
        except Exception as e:
            self.worker_finished.emit(self.worker_id, False, f"Error: {e}", 0, 0)
    
    def _run_analysis(self) -> None:
        """Execute the analysis workflow."""
        
        # Initialize engine
        self._log(f"Loading engine: {self.config.engine_path.name}")
        self.engine = EngineManager()
        
        try:
            self.engine.load(self.config.engine_path, self.uci_options, self.priority)
            hash_mb = self.uci_options.get('Hash', '?')
            threads = self.uci_options.get('Threads', '?')
            self._log(f"Engine ready: {self.engine.engine_name} (Hash={hash_mb}MB, Threads={threads})")
        except Exception as e:
            self.worker_finished.emit(self.worker_id, False, f"Failed to load engine: {e}", 0, 0)
            return
        
        # Log search limits
        limit_str = self.config.get_search_limit_display()
        self._log(f"Search limit: {limit_str}")
        
        # Initialize writers
        pgn_writer = None
        polyglot_writer = None
        
        if self.config.pgn_enabled and self.temp_pgn_path:
            pgn_writer = PGNWriter(self.temp_pgn_path, self.config.split_size_mb)
        
        if self.config.bin_enabled and self.temp_bin_path:
            polyglot_writer = PolyglotWriter()
        
        # Count assigned games
        total_assigned = len(self.game_indices)
        self._log(f"Assigned {total_assigned} games")
        
        if total_assigned == 0:
            self.worker_finished.emit(self.worker_id, True, "No games assigned", 0, 0)
            return
        
        # Generate analysis plies
        analysis_plies = generate_analysis_plies(self.config)
        
        # Process games
        games_processed = 0
        total_positions = 0
        
        for game_index, game in FileManager.iterate_games_with_index(self.config.input_pgn):
            if self._stop_requested:
                self._log("Stopping...")
                break
            
            # Skip games not assigned to this worker
            if game_index not in self.game_indices:
                continue
            
            games_processed += 1
            self.progress.emit(self.worker_id, games_processed, total_assigned)
            
            # Get game identifier
            white = game.headers.get("White", "?")
            black = game.headers.get("Black", "?")
            self._log(f"Game {games_processed}/{total_assigned}: {white} vs {black}")
            
            # Analyze game
            analyzed_game, positions = self._analyze_game(game, analysis_plies, polyglot_writer)
            total_positions += positions
            
            # Write PGN
            if pgn_writer and analyzed_game:
                output_path = pgn_writer.write_game(analyzed_game)
                self.game_completed.emit(self.worker_id, str(output_path))
        
        # Write Polyglot book
        if polyglot_writer and self.temp_bin_path:
            entries = polyglot_writer.write(self.temp_bin_path)
            self._log(f"Wrote {entries} book entries")
        
        # Cleanup
        self.engine.close()
        
        # Report completion
        if self._stop_requested:
            self.worker_finished.emit(
                self.worker_id, True,
                f"Stopped: {games_processed} games, {total_positions} positions",
                games_processed, total_positions
            )
        else:
            self.worker_finished.emit(
                self.worker_id, True,
                f"Complete: {games_processed} games, {total_positions} positions",
                games_processed, total_positions
            )
    
    def _analyze_game(
        self,
        game: chess.pgn.Game,
        analysis_plies: List[int],
        polyglot_writer: Optional[PolyglotWriter]
    ) -> tuple[chess.pgn.Game, int]:
        """
        Analyze a single game at specified plies.
        
        Args:
            game: Input game
            analysis_plies: Plies to analyze
            polyglot_writer: Optional Polyglot writer
            
        Returns:
            (New game with analysis variations, positions analyzed count)
        """
        # Create output game
        output_game = chess.pgn.Game()
        
        # Copy headers
        for key, value in game.headers.items():
            output_game.headers[key] = value
        
        # Override some headers
        output_game.headers["Event"] = "Interval Analysis"
        output_game.headers["Site"] = "Localhost"
        output_game.headers["Result"] = "*"
        
        # Add engine info
        if self.engine:
            perspective = "White" if self.config.perspective == Perspective.WHITE else "Black"
            output_game.headers["Annotator"] = self.engine.engine_name
        
        # Navigate through game
        board = game.board()
        node = game
        output_node = output_game
        current_ply = 0
        positions_analyzed = 0
        
        while node.variations:
            move = node.variation(0).move
            current_ply += 1
            
            # Check if we should analyze this position
            if current_ply in analysis_plies:
                # Only analyze if it's our perspective's turn
                is_white_turn = board.turn == chess.WHITE
                should_analyze = (
                    (self.config.perspective == Perspective.WHITE and is_white_turn) or
                    (self.config.perspective == Perspective.BLACK and not is_white_turn)
                )
                
                if should_analyze:
                    results = self._analyze_position(board, current_ply)
                    positions_analyzed += 1
                    
                    if results:
                        # Add to Polyglot book
                        if polyglot_writer:
                            for rank, result in enumerate(results):
                                polyglot_writer.add_entry(board, result.move, rank)
                        
                        # Add variations to PGN
                        for i, result in enumerate(results):
                            if i == 0:
                                # Main line - add PV as continuation
                                self._add_pv_to_node(output_node, board.copy(), result.pv)
                            else:
                                # Variation
                                self._add_variation(output_node, board.copy(), result.pv)
            
            # Make the move
            board.push(move)
            node = node.variation(0)
            output_node = output_node.add_variation(move)
        
        return output_game, positions_analyzed
    
    def _analyze_position(self, board: chess.Board, ply: int) -> List[AnalysisResult]:
        """
        Analyze a position and filter by tolerance.
        
        Returns:
            List of acceptable moves
        """
        if not self.engine:
            return []
        
        results = self.engine.analyze(
            board,
            depth_limit=self.config.depth_limit,
            time_limit=self.config.time_limit,
            multipv=self.config.candidates
        )
        
        if not results:
            return []
        
        # Format position info
        move_num, side = ply_to_move(ply)
        if side == 'White':
            pos_str = f"{move_num}."
        else:
            pos_str = f"{move_num}..."
        
        # Filter by tolerance
        best_score = results[0].score_cp
        accepted = []
        
        for i, result in enumerate(results):
            # Always accept mate scores
            if result.is_mate:
                accepted.append(result)
                
                # Log the analysis
                move_san = board.san(result.move)
                pv_str = result.pv_san(board, 5)
                self._emit_analysis(pos_str, i + 1, move_san, result.score_display(), result.depth, pv_str)
                continue
            
            # Skip if best score is mate but this isn't
            if best_score is None:
                continue
            
            if result.score_cp is None:
                continue
            
            # Check tolerance
            diff = abs(best_score - result.score_cp)
            if diff <= self.config.tolerance:
                accepted.append(result)
                
                # Log the analysis
                move_san = board.san(result.move)
                pv_str = result.pv_san(board, 5)
                self._emit_analysis(pos_str, i + 1, move_san, result.score_display(), result.depth, pv_str)
        
        return accepted
    
    def _emit_analysis(self, pos: str, candidate: int, move: str, score: str, depth: int, pv: str) -> None:
        """Emit formatted analysis line."""
        if candidate == 1:
            prefix = "→"
        else:
            prefix = f"  {candidate})"
        
        line = f"  {pos} {prefix} {move} [{score}] d{depth} │ {pv}"
        self.position_analyzed.emit(self.worker_id, line)
    
    def _add_pv_to_node(
        self,
        node: chess.pgn.GameNode,
        board: chess.Board,
        pv: List[chess.Move]
    ) -> None:
        """Add principal variation moves to a node."""
        current = node
        moves_added = 0
        
        for move in pv:
            if moves_added >= self.config.extension:
                break
            
            if move not in board.legal_moves:
                break
            
            current = current.add_variation(move)
            board.push(move)
            moves_added += 1
    
    def _add_variation(
        self,
        node: chess.pgn.GameNode,
        board: chess.Board,
        pv: List[chess.Move]
    ) -> None:
        """Add a variation branch from current node."""
        if not pv:
            return
        
        # First move creates the variation
        first_move = pv[0]
        if first_move not in board.legal_moves:
            return
        
        var_node = node.add_variation(first_move)
        board.push(first_move)
        
        # Add remaining PV moves
        moves_added = 1
        for move in pv[1:]:
            if moves_added >= self.config.extension:
                break
            
            if move not in board.legal_moves:
                break
            
            var_node = var_node.add_variation(move)
            board.push(move)
            moves_added += 1