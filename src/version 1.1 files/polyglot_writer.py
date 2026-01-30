"""Polyglot opening book writer."""

import struct
from pathlib import Path
from typing import List, Tuple
import chess
import chess.polyglot


# Weight assignments by candidate rank
CANDIDATE_WEIGHTS = {
    0: 100,  # Best move
    1: 50,   # Second best
    2: 25,   # Third best
}


class PolyglotWriter:
    """Accumulates positions and writes Polyglot .bin format."""
    
    def __init__(self):
        self.entries: List[Tuple[int, int, int]] = []  # (hash, encoded_move, weight)
    
    def add_entry(self, board: chess.Board, move: chess.Move, candidate_rank: int = 0) -> None:
        """
        Add a position/move pair to the book.
        
        Args:
            board: Position BEFORE the move is made
            move: The move to record
            candidate_rank: 0 = best, 1 = second, 2 = third
        """
        pos_hash = chess.polyglot.zobrist_hash(board)
        encoded_move = self._encode_move(move)
        weight = CANDIDATE_WEIGHTS.get(candidate_rank, 25)
        
        self.entries.append((pos_hash, encoded_move, weight))
    
    def _encode_move(self, move: chess.Move) -> int:
        """
        Encode move in Polyglot format.
        
        Bits 0-2: to file
        Bits 3-5: to rank
        Bits 6-8: from file
        Bits 9-11: from rank
        Bits 12-14: promotion piece (0=none, 1=n, 2=b, 3=r, 4=q)
        """
        to_file = chess.square_file(move.to_square)
        to_rank = chess.square_rank(move.to_square)
        from_file = chess.square_file(move.from_square)
        from_rank = chess.square_rank(move.from_square)
        
        promotion = 0
        if move.promotion:
            promotion_map = {
                chess.KNIGHT: 1,
                chess.BISHOP: 2,
                chess.ROOK: 3,
                chess.QUEEN: 4,
            }
            promotion = promotion_map.get(move.promotion, 0)
        
        encoded = (
            to_file |
            (to_rank << 3) |
            (from_file << 6) |
            (from_rank << 9) |
            (promotion << 12)
        )
        
        return encoded
    
    def write(self, path: Path) -> int:
        """
        Write accumulated entries to .bin file.
        
        Entries are sorted by hash. Duplicate hash+move pairs
        have their weights summed (capped at 65535).
        
        Args:
            path: Output file path
            
        Returns:
            Number of entries written
        """
        if not self.entries:
            return 0
        
        # Merge duplicates
        merged = self._merge_duplicates()
        
        # Sort by hash
        merged.sort(key=lambda x: x[0])
        
        # Write binary
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            for pos_hash, encoded_move, weight in merged:
                # Polyglot entry: 16 bytes
                # uint64 key, uint16 move, uint16 weight, uint32 learn
                entry = struct.pack('>QHHi', pos_hash, encoded_move, weight, 0)
                f.write(entry)
        
        return len(merged)
    
    def _merge_duplicates(self) -> List[Tuple[int, int, int]]:
        """Merge entries with same hash+move, summing weights."""
        merged_dict = {}
        
        for pos_hash, encoded_move, weight in self.entries:
            key = (pos_hash, encoded_move)
            if key in merged_dict:
                # Sum weights, cap at 65535 (uint16 max)
                merged_dict[key] = min(65535, merged_dict[key] + weight)
            else:
                merged_dict[key] = weight
        
        return [(h, m, w) for (h, m), w in merged_dict.items()]
    
    def clear(self) -> None:
        """Clear all accumulated entries."""
        self.entries.clear()
    
    def entry_count(self) -> int:
        """Return number of accumulated entries (pre-merge)."""
        return len(self.entries)