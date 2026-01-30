"""UCI Engine Configuration Dialog."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QLineEdit, QCheckBox, QComboBox,
    QPushButton, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any, Optional
import chess.engine
from pathlib import Path


class UCIConfigDialog(QDialog):
    """Dialog for configuring UCI engine options."""
    
    def __init__(self, engine_path: Path, parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.engine_name = "Unknown Engine"
        self.options: Dict[str, Any] = {}
        self.option_widgets: Dict[str, Any] = {}
        
        self.setWindowTitle("UCI Engine Configuration")
        self.setMinimumWidth(450)
        self.setModal(True)
        
        self._load_engine()
        self._setup_ui()
    
    def _load_engine(self) -> None:
        """Load engine and get available options."""
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(str(self.engine_path))
            self.engine_name = self.engine.id.get("name", self.engine_path.stem)
            
            # Get UCI options
            for name, option in self.engine.options.items():
                self.options[name] = {
                    'type': option.type,
                    'default': option.default,
                    'min': option.min,
                    'max': option.max,
                    'var': option.var if hasattr(option, 'var') else None,
                    'value': option.default
                }
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", f"Failed to load engine:\n{e}")
    
    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Engine info
        info_group = QGroupBox("Engine Information")
        info_layout = QFormLayout(info_group)
        info_layout.addRow("Name:", QLabel(self.engine_name))
        info_layout.addRow("Path:", QLabel(str(self.engine_path)))
        layout.addWidget(info_group)
        
        # Common options
        common_group = QGroupBox("Common Settings")
        common_layout = QFormLayout(common_group)
        
        # Hash
        if 'Hash' in self.options:
            opt = self.options['Hash']
            spin = QSpinBox()
            spin.setRange(opt.get('min', 1), min(opt.get('max', 65536), 65536))
            spin.setValue(opt.get('default', 128))
            spin.setSuffix(" MB")
            self.option_widgets['Hash'] = spin
            common_layout.addRow("Hash:", spin)
        
        # Threads
        if 'Threads' in self.options:
            opt = self.options['Threads']
            spin = QSpinBox()
            spin.setRange(opt.get('min', 1), min(opt.get('max', 512), 512))
            spin.setValue(opt.get('default', 1))
            self.option_widgets['Threads'] = spin
            common_layout.addRow("Threads:", spin)
        
        # Ponder (disable for analysis)
        if 'Ponder' in self.options:
            check = QCheckBox()
            check.setChecked(False)  # Disable ponder for analysis
            self.option_widgets['Ponder'] = check
            common_layout.addRow("Ponder:", check)
        
        layout.addWidget(common_group)
        
        # Syzygy/Tablebase path if available
        tb_group = QGroupBox("Tablebases (Optional)")
        tb_layout = QFormLayout(tb_group)
        
        if 'SyzygyPath' in self.options:
            line = QLineEdit()
            line.setPlaceholderText("Path to Syzygy tablebases...")
            self.option_widgets['SyzygyPath'] = line
            tb_layout.addRow("Syzygy Path:", line)
            layout.addWidget(tb_group)
        elif 'NalimovPath' in self.options:
            line = QLineEdit()
            line.setPlaceholderText("Path to Nalimov tablebases...")
            self.option_widgets['NalimovPath'] = line
            tb_layout.addRow("Nalimov Path:", line)
            layout.addWidget(tb_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.defaults_btn = QPushButton("Reset Defaults")
        self.defaults_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(self.defaults_btn)
        
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)
        
        layout.addLayout(btn_layout)
    
    def _reset_defaults(self) -> None:
        """Reset all options to defaults."""
        for name, widget in self.option_widgets.items():
            if name in self.options:
                default = self.options[name].get('default')
                if isinstance(widget, QSpinBox):
                    widget.setValue(default if default else 1)
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(default))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(default) if default else "")
    
    def get_uci_options(self) -> Dict[str, Any]:
        """Get configured UCI options."""
        result = {}
        
        for name, widget in self.option_widgets.items():
            if isinstance(widget, QSpinBox):
                result[name] = widget.value()
            elif isinstance(widget, QCheckBox):
                result[name] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    result[name] = text
            elif isinstance(widget, QComboBox):
                result[name] = widget.currentText()
        
        return result
    
    def get_engine_name(self) -> str:
        """Return detected engine name."""
        return self.engine_name
    
    def closeEvent(self, event) -> None:
        """Clean up engine on close."""
        if self.engine:
            try:
                self.engine.quit()
            except:
                pass
        super().closeEvent(event)
    
    def reject(self) -> None:
        """Clean up on cancel."""
        if self.engine:
            try:
                self.engine.quit()
            except:
                pass
        super().reject()
    
    def accept(self) -> None:
        """Clean up on accept."""
        if self.engine:
            try:
                self.engine.quit()
            except:
                pass
        super().accept()