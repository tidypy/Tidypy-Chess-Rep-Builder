"""Analysis configuration dataclass with validation and presets."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path
import os

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class Perspective(Enum):
    WHITE = "white"
    BLACK = "black"


class Preset(Enum):
    QUICK_SCAN = "Quick Scan"
    DEEP_PREP = "Deep Prep"
    BLITZ_REPERTOIRE = "Blitz Repertoire"
    CUSTOM = "Custom"


class Priority(Enum):
    LOW = "Low"
    BELOW_NORMAL = "Below Normal"
    NORMAL = "Normal"


# Preset definitions: (skip, increment, max_move, extension, candidates, tolerance, depth_limit, time_limit)
PRESET_VALUES = {
    Preset.QUICK_SCAN: (0, 10, 20, 3, 1, 200, 12, 1.0),
    Preset.DEEP_PREP: (0, 5, 30, 8, 2, 75, 20, 5.0),
    Preset.BLITZ_REPERTOIRE: (0, 7, 24, 5, 1, 150, 16, 2.0),
}


@dataclass
class SystemResources:
    """Detected system resources."""
    total_cores: int = 4
    total_ram_gb: float = 8.0
    available_cores: int = 2
    available_ram_gb: float = 4.0
    recommended_workers: int = 1
    threads_per_worker: int = 1
    hash_per_worker: int = 256
    
    @classmethod
    def detect(cls, reserve_cores: int = 2, reserve_ram_gb: float = 4.0) -> 'SystemResources':
        """Detect system resources and calculate recommendations."""
        total_cores = os.cpu_count() or 4
        
        if PSUTIL_AVAILABLE:
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
        else:
            total_ram_gb = 8.0  # Default assumption
        
        available_cores = max(1, total_cores - reserve_cores)
        available_ram_gb = max(1.0, total_ram_gb - reserve_ram_gb)
        
        # Calculate optimal workers
        max_workers_by_cores = available_cores
        max_workers_by_ram = int(available_ram_gb / 0.5)  # 512MB minimum per worker
        
        recommended_workers = min(max_workers_by_cores, max_workers_by_ram, 4)  # Cap at 4
        recommended_workers = max(1, recommended_workers)
        
        # Distribute resources
        threads_per_worker = max(1, available_cores // recommended_workers)
        hash_per_worker = max(128, int((available_ram_gb * 1024) / recommended_workers * 0.7))
        hash_per_worker = min(hash_per_worker, 2048)  # Cap at 2GB per worker
        
        return cls(
            total_cores=total_cores,
            total_ram_gb=round(total_ram_gb, 1),
            available_cores=available_cores,
            available_ram_gb=round(available_ram_gb, 1),
            recommended_workers=recommended_workers,
            threads_per_worker=threads_per_worker,
            hash_per_worker=hash_per_worker,
        )
    
    def summary(self) -> str:
        """Return human-readable summary."""
        return f"{self.total_cores} cores, {self.total_ram_gb}GB RAM"
    
    def usage_summary(self, workers: int) -> str:
        """Return usage summary for given worker count."""
        if workers <= 0:
            workers = self.recommended_workers
        threads = self.threads_per_worker * workers
        hash_total = (self.hash_per_worker * workers) / 1024
        return f"{workers} workers × {self.threads_per_worker} threads × {self.hash_per_worker}MB = {threads} threads, {hash_total:.1f}GB"


@dataclass
class AnalysisConfig:
    """Complete configuration for interval analysis."""
    
    # Engine
    engine_path: Path = field(default_factory=lambda: Path())
    engine_name: str = "Unknown Engine"
    uci_options: Dict[str, Any] = field(default_factory=dict)
    
    # Files
    input_pgn: Path = field(default_factory=lambda: Path())
    output_pgn: Optional[Path] = None
    output_bin: Optional[Path] = None
    pgn_enabled: bool = True
    bin_enabled: bool = True
    split_size_mb: int = 10
    
    # Perspective
    perspective: Perspective = Perspective.WHITE
    
    # Interval settings
    skip_first: int = 0
    increment: int = 7
    max_move: int = 24
    extension: int = 5
    
    # Advanced
    candidates: int = 1
    tolerance: int = 150
    depth_limit: int = 16      # 0 = no limit, stops at depth OR time
    time_limit: float = 2.0    # 0 = no limit, stops at depth OR time
    
    # Performance
    num_workers: int = 0  # 0 = auto
    priority: Priority = Priority.BELOW_NORMAL
    
    # Preset tracking
    preset: Preset = Preset.BLITZ_REPERTOIRE
    
    # Constraints
    CONSTRAINTS = {
        'skip_first': (0, 20),
        'increment': (5, 15),
        'max_move': (10, 37),
        'extension': (3, 10),
        'candidates': (1, 3),
        'tolerance': (50, 500),
        'depth_limit': (0, 30),
        'time_limit': (0.0, 30.0),
        'split_size_mb': (1, 50),
        'num_workers': (0, 4),
    }
    
    def __post_init__(self):
        """Validate all parameters."""
        self.validate()
    
    def validate(self) -> None:
        """Enforce constraints on all parameters."""
        for param, (min_val, max_val) in self.CONSTRAINTS.items():
            value = getattr(self, param)
            clamped = max(min_val, min(max_val, value))
            setattr(self, param, type(value)(clamped))
        
        # At least one output must be enabled
        if not self.pgn_enabled and not self.bin_enabled:
            self.pgn_enabled = True
        
        # At least one limit must be set
        if self.depth_limit == 0 and self.time_limit == 0.0:
            self.depth_limit = 16  # Default fallback
    
    def get_effective_workers(self, resources: SystemResources) -> int:
        """Get actual worker count (resolve auto)."""
        if self.num_workers <= 0:
            return resources.recommended_workers
        return self.num_workers
    
    def get_worker_uci_options(self, resources: SystemResources) -> Dict[str, Any]:
        """Get UCI options divided among workers."""
        workers = self.get_effective_workers(resources)
        
        options = self.uci_options.copy()
        
        # Divide hash among workers
        if 'Hash' in options:
            options['Hash'] = max(64, options['Hash'] // workers)
        else:
            options['Hash'] = resources.hash_per_worker
        
        # Divide threads among workers
        if 'Threads' in options:
            options['Threads'] = max(1, options['Threads'] // workers)
        else:
            options['Threads'] = resources.threads_per_worker
        
        return options
    
    def get_search_limit_display(self) -> str:
        """Return human-readable search limit description."""
        parts = []
        if self.depth_limit > 0:
            parts.append(f"d{self.depth_limit}")
        if self.time_limit > 0:
            parts.append(f"{self.time_limit}s")
        
        if len(parts) == 2:
            return f"{parts[0]} or {parts[1]}"
        elif len(parts) == 1:
            return parts[0]
        else:
            return "unlimited"
    
    def apply_preset(self, preset: Preset) -> None:
        """Load values from a preset."""
        if preset == Preset.CUSTOM:
            self.preset = preset
            return
        
        values = PRESET_VALUES.get(preset)
        if values:
            (self.skip_first, self.increment, self.max_move, 
             self.extension, self.candidates, self.tolerance, 
             self.depth_limit, self.time_limit) = values
            self.preset = preset
            self.validate()
    
    def to_dict(self) -> dict:
        """Export configuration as dictionary."""
        return {
            'engine_path': str(self.engine_path),
            'engine_name': self.engine_name,
            'uci_options': self.uci_options,
            'input_pgn': str(self.input_pgn),
            'output_pgn': str(self.output_pgn) if self.output_pgn else None,
            'output_bin': str(self.output_bin) if self.output_bin else None,
            'pgn_enabled': self.pgn_enabled,
            'bin_enabled': self.bin_enabled,
            'split_size_mb': self.split_size_mb,
            'perspective': self.perspective.value,
            'skip_first': self.skip_first,
            'increment': self.increment,
            'max_move': self.max_move,
            'extension': self.extension,
            'candidates': self.candidates,
            'tolerance': self.tolerance,
            'depth_limit': self.depth_limit,
            'time_limit': self.time_limit,
            'num_workers': self.num_workers,
            'priority': self.priority.value,
            'preset': self.preset.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AnalysisConfig':
        """Create configuration from dictionary."""
        config = cls()
        config.engine_path = Path(data.get('engine_path', ''))
        config.engine_name = data.get('engine_name', 'Unknown Engine')
        config.uci_options = data.get('uci_options', {})
        config.input_pgn = Path(data.get('input_pgn', ''))
        config.output_pgn = Path(data['output_pgn']) if data.get('output_pgn') else None
        config.output_bin = Path(data['output_bin']) if data.get('output_bin') else None
        config.pgn_enabled = data.get('pgn_enabled', True)
        config.bin_enabled = data.get('bin_enabled', True)
        config.split_size_mb = data.get('split_size_mb', 10)
        config.perspective = Perspective(data.get('perspective', 'white'))
        config.skip_first = data.get('skip_first', 0)
        config.increment = data.get('increment', 7)
        config.max_move = data.get('max_move', 24)
        config.extension = data.get('extension', 5)
        config.candidates = data.get('candidates', 1)
        config.tolerance = data.get('tolerance', 150)
        config.depth_limit = data.get('depth_limit', 16)
        config.time_limit = data.get('time_limit', 2.0)
        config.num_workers = data.get('num_workers', 0)
        config.priority = Priority(data.get('priority', 'Below Normal'))
        config.preset = Preset(data.get('preset', 'Blitz Repertoire'))
        config.validate()
        return config