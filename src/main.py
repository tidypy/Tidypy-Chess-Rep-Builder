"""Tidypy - Chess Repertoire Builder - Main GUI"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from typing import List, Optional, Dict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QRadioButton, QButtonGroup, QCheckBox, QTextEdit,
    QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from qt_material import apply_stylesheet

from config import AnalysisConfig, Perspective, Preset, Priority, SystemResources
from worker import AnalysisWorker
from file_manager import FileManager
from pgn_writer import PGNWriter
from polyglot_writer import PolyglotWriter
from uci_dialog import UCIConfigDialog


class TidypyWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = AnalysisConfig()
        self.workers: List[AnalysisWorker] = []
        self.uci_options = {}
        self.engine_name = ""
        self.resources = SystemResources.detect()
        
        # Track worker completion
        self.workers_finished = 0
        self.total_games_processed = 0
        self.total_positions_analyzed = 0
        self.worker_errors: List[str] = []
        self.total_games = 0
        self.num_workers = 0
        self.current_config: Optional[AnalysisConfig] = None
        
        self.setWindowTitle("Tidypy - Chess Repertoire Builder")
        self.setMinimumSize(700, 900)
        
        self._setup_ui()
        self._connect_signals()
        self._apply_preset(Preset.BLITZ_REPERTOIRE)
        self._update_resource_display()
    
    def _setup_ui(self) -> None:
        """Build the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        
        # 1. Engine Section
        layout.addWidget(self._create_engine_section())
        
        # 2. Files Section
        layout.addWidget(self._create_files_section())
        
        # 3. Perspective Section
        layout.addWidget(self._create_perspective_section())
        
        # 4. Interval Settings Section
        layout.addWidget(self._create_interval_section())
        
        # 5. Performance Section
        layout.addWidget(self._create_performance_section())
        
        # 6. Controls Section
        layout.addWidget(self._create_controls_section())
        
        # 7. Status Section
        layout.addWidget(self._create_status_section())
        
        # 8. Log Section
        layout.addWidget(self._create_log_section())
    
    def _create_engine_section(self) -> QGroupBox:
        """Create engine configuration section."""
        group = QGroupBox("Engine")
        layout = QVBoxLayout(group)
        
        # Path row
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Path:"))
        self.engine_path = QLineEdit()
        self.engine_path.setPlaceholderText("Select engine executable...")
        self.engine_path.setReadOnly(True)
        path_row.addWidget(self.engine_path, 1)
        
        self.engine_browse = QPushButton("Browse")
        path_row.addWidget(self.engine_browse)
        layout.addLayout(path_row)
        
        # Engine info row
        info_row = QHBoxLayout()
        self.engine_info = QLabel("No engine selected")
        self.engine_info.setStyleSheet("color: gray; font-style: italic;")
        info_row.addWidget(self.engine_info)
        info_row.addStretch()
        
        self.engine_config_btn = QPushButton("Configure UCI")
        self.engine_config_btn.setEnabled(False)
        info_row.addWidget(self.engine_config_btn)
        layout.addLayout(info_row)
        
        return group
    
    def _create_files_section(self) -> QGroupBox:
        """Create files configuration section."""
        group = QGroupBox("Files")
        layout = QVBoxLayout(group)
        
        # Input PGN
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Input PGN:"))
        self.input_pgn = QLineEdit()
        self.input_pgn.setPlaceholderText("Select input PGN file...")
        row1.addWidget(self.input_pgn, 1)
        self.input_browse = QPushButton("Browse")
        row1.addWidget(self.input_browse)
        layout.addLayout(row1)
        
        # Output PGN
        row2 = QHBoxLayout()
        self.pgn_enabled = QCheckBox("Output PGN:")
        self.pgn_enabled.setChecked(True)
        row2.addWidget(self.pgn_enabled)
        self.output_pgn = QLineEdit()
        self.output_pgn.setPlaceholderText("Output PGN path...")
        row2.addWidget(self.output_pgn, 1)
        self.output_pgn_browse = QPushButton("Browse")
        row2.addWidget(self.output_pgn_browse)
        layout.addLayout(row2)
        
        # Output .bin
        row3 = QHBoxLayout()
        self.bin_enabled = QCheckBox("Output .bin:")
        self.bin_enabled.setChecked(True)
        row3.addWidget(self.bin_enabled)
        self.output_bin = QLineEdit()
        self.output_bin.setPlaceholderText("Output Polyglot book path...")
        row3.addWidget(self.output_bin, 1)
        self.output_bin_browse = QPushButton("Browse")
        row3.addWidget(self.output_bin_browse)
        layout.addLayout(row3)
        
        # Split size
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Split PGN at:"))
        self.split_size = QSpinBox()
        self.split_size.setRange(1, 50)
        self.split_size.setValue(10)
        self.split_size.setSuffix(" MB")
        row4.addWidget(self.split_size)
        row4.addStretch()
        layout.addLayout(row4)
        
        return group
    
    def _create_perspective_section(self) -> QGroupBox:
        """Create perspective selection section."""
        group = QGroupBox("Perspective")
        layout = QHBoxLayout(group)
        
        self.perspective_group = QButtonGroup(self)
        
        self.white_radio = QRadioButton("White Repertoire")
        self.white_radio.setChecked(True)
        self.perspective_group.addButton(self.white_radio)
        layout.addWidget(self.white_radio)
        
        self.black_radio = QRadioButton("Black Repertoire")
        self.perspective_group.addButton(self.black_radio)
        layout.addWidget(self.black_radio)
        
        layout.addStretch()
        
        return group
    
    def _create_interval_section(self) -> QGroupBox:
        """Create interval settings section."""
        group = QGroupBox("Interval Settings")
        layout = QVBoxLayout(group)
        
        # Preset
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        for preset in Preset:
            self.preset_combo.addItem(preset.value, preset)
        preset_row.addWidget(self.preset_combo)
        preset_row.addStretch()
        layout.addLayout(preset_row)
        
        # Main parameters
        params_row = QHBoxLayout()
        
        # Skip First
        params_row.addWidget(QLabel("Skip First:"))
        self.skip_first = QSpinBox()
        self.skip_first.setRange(0, 20)
        self.skip_first.setToolTip("Analyze every move up to this move number")
        params_row.addWidget(self.skip_first)
        
        # Increment
        params_row.addWidget(QLabel("Increment:"))
        self.increment = QSpinBox()
        self.increment.setRange(5, 15)
        self.increment.setToolTip("Moves between analysis intervals")
        params_row.addWidget(self.increment)
        
        # Max Move
        params_row.addWidget(QLabel("Max Move:"))
        self.max_move = QSpinBox()
        self.max_move.setRange(10, 37)
        self.max_move.setToolTip("Stop analysis after this move")
        params_row.addWidget(self.max_move)
        
        # Extension
        params_row.addWidget(QLabel("Extension:"))
        self.extension = QSpinBox()
        self.extension.setRange(3, 10)
        self.extension.setToolTip("PV moves to record at each interval")
        params_row.addWidget(self.extension)
        
        layout.addLayout(params_row)
        
        # Search parameters
        search_row = QHBoxLayout()
        
        # Depth
        search_row.addWidget(QLabel("Depth:"))
        self.depth_limit = QSpinBox()
        self.depth_limit.setRange(0, 30)
        self.depth_limit.setToolTip("Maximum search depth (0 = no limit)")
        self.depth_limit.setSpecialValueText("No limit")
        search_row.addWidget(self.depth_limit)
        
        # Time
        search_row.addWidget(QLabel("Time:"))
        self.time_limit = QDoubleSpinBox()
        self.time_limit.setRange(0.0, 30.0)
        self.time_limit.setSingleStep(0.5)
        self.time_limit.setSuffix(" sec")
        self.time_limit.setToolTip("Maximum time per position (0 = no limit)")
        self.time_limit.setSpecialValueText("No limit")
        search_row.addWidget(self.time_limit)
        
        # Candidates
        search_row.addWidget(QLabel("Candidates:"))
        self.candidates = QSpinBox()
        self.candidates.setRange(1, 3)
        self.candidates.setToolTip("Number of alternative moves (MultiPV)")
        search_row.addWidget(self.candidates)
        
        # Tolerance
        search_row.addWidget(QLabel("Tolerance:"))
        self.tolerance = QSpinBox()
        self.tolerance.setRange(50, 500)
        self.tolerance.setSuffix(" cp")
        self.tolerance.setToolTip("Max centipawn difference from best move")
        search_row.addWidget(self.tolerance)
        
        layout.addLayout(search_row)
        
        # Search limit info
        self.search_info = QLabel("ℹ️ Search stops when depth OR time limit is reached (whichever first)")
        self.search_info.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.search_info)
        
        return group
    
    def _create_performance_section(self) -> QGroupBox:
        """Create performance settings section."""
        group = QGroupBox("Performance")
        layout = QVBoxLayout(group)
        
        # Workers and priority row
        settings_row = QHBoxLayout()
        
        # Workers
        settings_row.addWidget(QLabel("Workers:"))
        self.workers_combo = QComboBox()
        self.workers_combo.addItem(f"Auto ({self.resources.recommended_workers})", 0)
        for i in range(1, 5):
            self.workers_combo.addItem(str(i), i)
        self.workers_combo.setToolTip("Number of parallel engine instances")
        settings_row.addWidget(self.workers_combo)
        
        settings_row.addSpacing(20)
        
        # Priority
        settings_row.addWidget(QLabel("Priority:"))
        self.priority_combo = QComboBox()
        for p in Priority:
            self.priority_combo.addItem(p.value, p)
        self.priority_combo.setCurrentIndex(1)  # Below Normal
        self.priority_combo.setToolTip("Engine process priority")
        settings_row.addWidget(self.priority_combo)
        
        settings_row.addStretch()
        layout.addLayout(settings_row)
        
        # Resource info
        self.resource_info = QLabel()
        self.resource_info.setStyleSheet("color: gray;")
        layout.addWidget(self.resource_info)
        
        return group
    
    def _create_controls_section(self) -> QGroupBox:
        """Create control buttons section."""
        group = QGroupBox("Controls")
        layout = QHBoxLayout(group)
        
        self.start_btn = QPushButton("▶  Start Analysis")
        self.start_btn.setMinimumHeight(40)
        layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹  Stop (Keep Work)")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)
        
        return group
    
    def _create_status_section(self) -> QGroupBox:
        """Create status display section."""
        group = QGroupBox("Status")
        layout = QVBoxLayout(group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Ready")
        layout.addWidget(self.progress_bar)
        
        # Status labels
        status_row = QHBoxLayout()
        self.game_label = QLabel("Games: 0/0")
        status_row.addWidget(self.game_label)
        
        self.worker_label = QLabel("Workers: 0/0")
        status_row.addWidget(self.worker_label)
        
        self.file_label = QLabel("Last saved: -")
        status_row.addWidget(self.file_label)
        status_row.addStretch()
        layout.addLayout(status_row)
        
        return group
    
    def _create_log_section(self) -> QGroupBox:
        """Create log output section."""
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        
        # Use monospace font for aligned output
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_text.setFont(font)
        
        layout.addWidget(self.log_text)
        
        self.clear_log_btn = QPushButton("Clear Log")
        layout.addWidget(self.clear_log_btn)
        
        return group
    
    def _connect_signals(self) -> None:
        """Connect UI signals to handlers."""
        # Browse buttons
        self.engine_browse.clicked.connect(self._browse_engine)
        self.engine_config_btn.clicked.connect(self._configure_engine)
        self.input_browse.clicked.connect(self._browse_input)
        self.output_pgn_browse.clicked.connect(self._browse_output_pgn)
        self.output_bin_browse.clicked.connect(self._browse_output_bin)
        
        # Preset
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        
        # Parameter changes -> mark as custom
        for widget in [self.skip_first, self.increment, self.max_move, 
                       self.extension, self.candidates, self.tolerance, self.depth_limit]:
            widget.valueChanged.connect(self._on_param_changed)
        self.time_limit.valueChanged.connect(self._on_param_changed)
        
        # Workers combo -> update resource display
        self.workers_combo.currentIndexChanged.connect(self._update_resource_display)
        
        # Controls
        self.start_btn.clicked.connect(self._start_analysis)
        self.stop_btn.clicked.connect(self._stop_analysis)
        self.clear_log_btn.clicked.connect(self.log_text.clear)
    
    def _update_resource_display(self) -> None:
        """Update resource usage display."""
        workers = self.workers_combo.currentData()
        if workers == 0:
            workers = self.resources.recommended_workers
        
        threads = self.resources.threads_per_worker * workers
        hash_total = (self.resources.hash_per_worker * workers) / 1024
        
        self.resource_info.setText(
            f"ℹ️ System: {self.resources.summary()} │ "
            f"Using: {workers} × {self.resources.threads_per_worker} threads, "
            f"{self.resources.hash_per_worker}MB hash each = {threads} threads, {hash_total:.1f}GB total"
        )
    
    def _browse_engine(self) -> None:
        """Browse for engine executable and open config dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Engine", "",
            "Executables (*.exe);;All Files (*)"
        )
        if path:
            self.engine_path.setText(path)
            self._open_uci_dialog(Path(path))
    
    def _open_uci_dialog(self, path: Path) -> None:
        """Open UCI configuration dialog."""
        dialog = UCIConfigDialog(path, self)
        
        if dialog.exec():
            self.uci_options = dialog.get_uci_options()
            self.engine_name = dialog.get_engine_name()
            
            # Update UI
            self.engine_config_btn.setEnabled(True)
            
            # Show engine info
            info_parts = [self.engine_name]
            if 'Hash' in self.uci_options:
                info_parts.append(f"Hash: {self.uci_options['Hash']}MB")
            if 'Threads' in self.uci_options:
                info_parts.append(f"Threads: {self.uci_options['Threads']}")
            
            self.engine_info.setText(" │ ".join(info_parts))
            self.engine_info.setStyleSheet("color: #4CAF50;")
        else:
            # User cancelled - clear engine selection if none previously
            if not self.engine_name:
                self.engine_path.clear()
                self.engine_info.setText("No engine selected")
                self.engine_info.setStyleSheet("color: gray; font-style: italic;")
                self.engine_config_btn.setEnabled(False)
    
    def _configure_engine(self) -> None:
        """Re-open UCI configuration dialog."""
        path_text = self.engine_path.text()
        if path_text:
            self._open_uci_dialog(Path(path_text))
    
    def _browse_input(self) -> None:
        """Browse for input PGN."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Input PGN", "",
            "PGN Files (*.pgn);;All Files (*)"
        )
        if path:
            self.input_pgn.setText(path)
            # Auto-fill output paths
            input_path = Path(path)
            self.output_pgn.setText(str(FileManager.generate_output_path(input_path)))
            self.output_bin.setText(str(FileManager.generate_bin_path(input_path)))
    
    def _browse_output_pgn(self) -> None:
        """Browse for output PGN."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output PGN", "",
            "PGN Files (*.pgn)"
        )
        if path:
            self.output_pgn.setText(path)
    
    def _browse_output_bin(self) -> None:
        """Browse for output .bin."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Polyglot Book", "",
            "Polyglot Books (*.bin)"
        )
        if path:
            self.output_bin.setText(path)
    
    def _on_preset_changed(self, index: int) -> None:
        """Handle preset selection."""
        preset = self.preset_combo.currentData()
        if preset and preset != Preset.CUSTOM:
            self._apply_preset(preset)
    
    def _apply_preset(self, preset: Preset) -> None:
        """Apply preset values to UI."""
        self.config.apply_preset(preset)
        
        self.skip_first.setValue(self.config.skip_first)
        self.increment.setValue(self.config.increment)
        self.max_move.setValue(self.config.max_move)
        self.extension.setValue(self.config.extension)
        self.candidates.setValue(self.config.candidates)
        self.tolerance.setValue(self.config.tolerance)
        self.depth_limit.setValue(self.config.depth_limit)
        self.time_limit.setValue(self.config.time_limit)
        
        # Update combo without triggering signal
        self.preset_combo.blockSignals(True)
        index = self.preset_combo.findData(preset)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)
    
    def _on_param_changed(self) -> None:
        """Mark preset as custom when parameters change."""
        self.preset_combo.blockSignals(True)
        index = self.preset_combo.findData(Preset.CUSTOM)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)
    
    def _build_config(self) -> AnalysisConfig:
        """Build config from UI values."""
        config = AnalysisConfig()
        
        config.engine_path = Path(self.engine_path.text())
        config.engine_name = self.engine_name
        config.uci_options = self.uci_options.copy()
        config.input_pgn = Path(self.input_pgn.text())
        config.output_pgn = Path(self.output_pgn.text()) if self.pgn_enabled.isChecked() else None
        config.output_bin = Path(self.output_bin.text()) if self.bin_enabled.isChecked() else None
        config.pgn_enabled = self.pgn_enabled.isChecked()
        config.bin_enabled = self.bin_enabled.isChecked()
        config.split_size_mb = self.split_size.value()
        
        config.perspective = Perspective.WHITE if self.white_radio.isChecked() else Perspective.BLACK
        
        config.skip_first = self.skip_first.value()
        config.increment = self.increment.value()
        config.max_move = self.max_move.value()
        config.extension = self.extension.value()
        config.candidates = self.candidates.value()
        config.tolerance = self.tolerance.value()
        config.depth_limit = self.depth_limit.value()
        config.time_limit = self.time_limit.value()
        
        config.num_workers = self.workers_combo.currentData()
        config.priority = self.priority_combo.currentData()
        
        config.validate()
        return config
    
    def _validate_inputs(self) -> tuple[bool, str]:
        """Validate all inputs before starting."""
        # Engine
        if not self.engine_path.text():
            return False, "Please select an engine"
        valid, msg = FileManager.validate_engine(Path(self.engine_path.text()))
        if not valid:
            return False, msg
        
        # Input PGN
        if not self.input_pgn.text():
            return False, "Please select an input PGN file"
        valid, msg = FileManager.validate_input_pgn(Path(self.input_pgn.text()))
        if not valid:
            return False, msg
        
        # At least one output
        if not self.pgn_enabled.isChecked() and not self.bin_enabled.isChecked():
            return False, "Please enable at least one output format"
        
        if self.pgn_enabled.isChecked() and not self.output_pgn.text():
            return False, "Please specify output PGN path"
        
        if self.bin_enabled.isChecked() and not self.output_bin.text():
            return False, "Please specify output .bin path"
        
        # At least one search limit
        if self.depth_limit.value() == 0 and self.time_limit.value() == 0:
            return False, "Please set at least one search limit (depth or time)"
        
        return True, "OK"
    
    def _start_analysis(self) -> None:
        """Start the analysis with multiple workers."""
        valid, msg = self._validate_inputs()
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return
        
        config = self._build_config()
        self.current_config = config
        
        # Get effective worker count
        self.num_workers = config.get_effective_workers(self.resources)
        
        # Count games
        self.total_games = FileManager.count_games(config.input_pgn)
        if self.total_games == 0:
            QMessageBox.warning(self, "Error", "No games found in input file")
            return
        
        # Distribute games among workers
        game_distribution = FileManager.distribute_games(self.total_games, self.num_workers)
        
        # Get worker-specific UCI options
        worker_uci = config.get_worker_uci_options(self.resources)
        
        # Reset state
        self.workers = []
        self.workers_finished = 0
        self.total_games_processed = 0
        self.total_positions_analyzed = 0
        self.worker_errors = []
        
        # Log startup
        self._on_log(-1, "═" * 60)
        self._on_log(-1, f"Starting analysis with {self.num_workers} worker(s)")
        self._on_log(-1, f"Total games: {self.total_games}")
        self._on_log(-1, f"Search limit: {config.get_search_limit_display()}")
        self._on_log(-1, f"Worker config: Hash={worker_uci.get('Hash', '?')}MB, Threads={worker_uci.get('Threads', '?')}")
        self._on_log(-1, "═" * 60)
        
        # Create workers
        for worker_id in range(self.num_workers):
            game_indices = game_distribution[worker_id]
            
            # Generate temp paths
            temp_pgn = None
            temp_bin = None
            
            if config.pgn_enabled and config.output_pgn:
                temp_pgn = FileManager.generate_temp_path(config.output_pgn, worker_id, '.pgn')
            
            if config.bin_enabled and config.output_bin:
                temp_bin = FileManager.generate_temp_path(config.output_bin, worker_id, '.bin')
            
            worker = AnalysisWorker(
                config=config,
                worker_id=worker_id,
                game_indices=game_indices,
                uci_options=worker_uci,
                priority=config.priority,
                temp_pgn_path=temp_pgn,
                temp_bin_path=temp_bin
            )
            
            # Connect signals
            worker.progress.connect(self._on_worker_progress)
            worker.log_message.connect(self._on_log)
            worker.game_completed.connect(self._on_game_completed)
            worker.worker_finished.connect(self._on_worker_finished)
            worker.position_analyzed.connect(self._on_position)
            
            self.workers.append(worker)
        
        # Update UI state
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setMaximum(self.total_games)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Starting workers...")
        self.worker_label.setText(f"Workers: 0/{self.num_workers}")
        
        # Start all workers
        for worker in self.workers:
            worker.start()
    
    def _stop_analysis(self) -> None:
        """Request stop of all workers."""
        self._on_log(-1, "⏹ Stop requested - finishing current games...")
        self.stop_btn.setEnabled(False)
        
        for worker in self.workers:
            worker.request_stop()
    
    def _on_worker_progress(self, worker_id: int, current: int, total: int) -> None:
        """Update progress from a worker."""
        # Calculate total progress across all workers
        total_current = sum(
            w.game_indices.__len__() if hasattr(w, '_games_done') else 0 
            for w in self.workers
        )
        
        # Simple approximation: use individual worker progress
        self.progress_bar.setValue(self.total_games_processed + current)
        self.progress_bar.setFormat(f"Worker {worker_id + 1}: {current}/{total}")
    
    def _on_log(self, worker_id: int, message: str) -> None:
        """Add message to log."""
        if worker_id >= 0:
            prefix = f"[W{worker_id + 1}] "
        else:
            prefix = ""
        
        self.log_text.append(f"{prefix}{message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_position(self, worker_id: int, analysis: str) -> None:
        """Handle position analysis output."""
        self._on_log(worker_id, analysis)
    
    def _on_game_completed(self, worker_id: int, filename: str) -> None:
        """Update when a game is completed."""
        self.total_games_processed += 1
        self.game_label.setText(f"Games: {self.total_games_processed}/{self.total_games}")
        self.progress_bar.setValue(self.total_games_processed)
        self.file_label.setText(f"Last saved: {Path(filename).name}")
    
    def _on_worker_finished(self, worker_id: int, success: bool, message: str, games: int, positions: int) -> None:
        """Handle worker completion."""
        self.workers_finished += 1
        self.total_positions_analyzed += positions
        
        if not success:
            self.worker_errors.append(f"Worker {worker_id + 1}: {message}")
        
        self._on_log(worker_id, f"Finished: {message}")
        self.worker_label.setText(f"Workers: {self.workers_finished}/{self.num_workers}")
        
        # Check if all workers done
        if self.workers_finished >= self.num_workers:
            self._finalize_analysis()
    
    def _finalize_analysis(self) -> None:
        """Merge outputs and clean up after all workers finish."""
        config = self.current_config
        if not config:
            return
        
        self._on_log(-1, "")
        self._on_log(-1, "═" * 60)
        self._on_log(-1, "Merging outputs...")
        
        # Collect temp file paths
        temp_pgns = []
        temp_bins = []
        
        for worker_id in range(self.num_workers):
            if config.pgn_enabled and config.output_pgn:
                temp_path = FileManager.generate_temp_path(config.output_pgn, worker_id, '.pgn')
                if temp_path.exists():
                    temp_pgns.append(temp_path)
            
            if config.bin_enabled and config.output_bin:
                temp_path = FileManager.generate_temp_path(config.output_bin, worker_id, '.bin')
                if temp_path.exists():
                    temp_bins.append(temp_path)
        
        # Merge PGN files
        if temp_pgns and config.output_pgn:
            games_merged = PGNWriter.merge_files(temp_pgns, config.output_pgn)
            self._on_log(-1, f"📄 Merged {games_merged} games to {config.output_pgn.name}")
        
        # Merge Polyglot books
        if temp_bins and config.output_bin:
            entries_merged = PolyglotWriter.merge_files(temp_bins, config.output_bin)
            self._on_log(-1, f"📚 Merged {entries_merged} book entries to {config.output_bin.name}")
        
        # Clean up temp files
        if config.output_pgn:
            FileManager.cleanup_temp_files(config.output_pgn, self.num_workers)
        if config.output_bin:
            FileManager.cleanup_temp_files(config.output_bin, self.num_workers)
        
        self._on_log(-1, "🧹 Cleaned up temporary files")
        
        # Final summary
        self._on_log(-1, "═" * 60)
        
        if self.worker_errors:
            for error in self.worker_errors:
                self._on_log(-1, f"⚠️ {error}")
        
        self._on_log(-1, f"✓ Complete: {self.total_games_processed} games, {self.total_positions_analyzed} positions")
        self._on_log(-1, "═" * 60)
        
        # Update UI
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setFormat("Complete")
        
        # Show completion message
        if self.worker_errors:
            QMessageBox.warning(
                self, "Complete with Errors",
                f"Processed {self.total_games_processed} games with {len(self.worker_errors)} error(s).\n"
                f"Check the log for details."
            )
        else:
            QMessageBox.information(
                self, "Complete",
                f"Successfully processed {self.total_games_processed} games.\n"
                f"Analyzed {self.total_positions_analyzed} positions."
            )
        
        # Clear workers
        self.workers = []
        self.current_config = None


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    
    # Apply theme
    apply_stylesheet(app, theme='dark_teal.xml')
    
    window = TidypyWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()