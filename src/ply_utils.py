"""Ply conversion utilities for perspective-aware analysis."""

from config import Perspective


def move_to_ply(move_number: int, perspective: Perspective) -> int:
    """
    Convert move number to ply.
    
    Move 1 White = ply 1
    Move 1 Black = ply 2
    Move 2 White = ply 3
    etc.
    """
    base_ply = (move_number - 1) * 2 + 1
    if perspective == Perspective.BLACK:
        base_ply += 1
    return base_ply


def ply_to_move(ply: int) -> tuple[int, str]:
    """
    Convert ply to move number and side.
    
    Returns: (move_number, 'White' or 'Black')
    """
    move_number = (ply + 1) // 2
    side = 'White' if ply % 2 == 1 else 'Black'
    return move_number, side


def generate_analysis_plies(config) -> list[int]:
    """
    Generate list of plies to analyze based on config.
    
    Phase A (Opening): Every move from ply 1 to skip_first
    Phase B (Intervals): Jump by increment until max_move
    
    Args:
        config: AnalysisConfig instance
        
    Returns:
        List of plies to analyze (for the selected perspective only)
    """
    plies = []
    
    # Determine starting ply based on perspective
    start_ply = 1 if config.perspective == Perspective.WHITE else 2
    
    # Calculate max ply
    max_ply = move_to_ply(config.max_move, config.perspective)
    
    # Phase A: Opening phase - analyze every move up to skip_first
    if config.skip_first > 0:
        skip_ply = move_to_ply(config.skip_first, config.perspective)
        current = start_ply
        while current <= skip_ply and current <= max_ply:
            plies.append(current)
            current += 2  # Next move for same color
    
    # Phase B: Interval phase
    # Start after the opening phase
    if config.skip_first > 0:
        interval_start_move = config.skip_first + config.increment
    else:
        interval_start_move = config.increment
    
    interval_start_ply = move_to_ply(interval_start_move, config.perspective)
    ply_step = config.increment * 2  # Increment is in moves, convert to plies
    
    current = interval_start_ply
    while current <= max_ply:
        if current not in plies:  # Avoid duplicates from Phase A
            plies.append(current)
        current += ply_step
    
    return sorted(plies)


def should_analyze_position(ply: int, analysis_plies: list[int]) -> bool:
    """Check if a position at given ply should be analyzed."""
    return ply in analysis_plies


def format_ply_for_display(ply: int) -> str:
    """Format ply as human-readable move notation."""
    move_num, side = ply_to_move(ply)
    if side == 'White':
        return f"{move_num}."
    else:
        return f"{move_num}..."