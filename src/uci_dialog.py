"""UCI Engine Configuration Dialog."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QSpinBox, QCheckBox, QLineEdit, QComboBox, QPushButton,
    QFormLayout, QFileDialog, QScrollArea, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt
import subprocess
import os
from typing import Dict, Any, Optional
from pathlib import Path


class UCIConfigDialog(QDialog):
    """Dialog for configuring UCI engine options."""
    # Options to always skip (never display)
    SKIP_OPTIONS = {'Ponder', 'UCI_Chess960', 'UCI_ShowWDL', 'UCI_LimitStrength'}
    
    # Options that belong in Resource Settings group
    RESOURCE_OPTIONS = {'Hash', 'Threads', 'SyzygyPath', 'SyzygyProbeDepth', 'SyzygyProbeLimit'}
    
    def __init__(self, engine_path: Path, parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self._engine_options: Dict[str, Any] = {}
        self._option_widgets: Dict[str, QWidget] = {}
        self._current_settings = parent.uci_options if parent and hasattr(parent, 'uci_options') else {}
        self.engine_name = "Unknown Engine"
        
        self.setWindowTitle("UCI Engine Configuration")
        self.setModal(True)
        
        self._load_engine()
        self._setup_ui()

    def _load_engine(self) -> None:
        """Parse 'uci' output from engine to get all available options."""
        if not self.engine_path.exists():
            QMessageBox.warning(self, "Engine Not Found", f"Could not find engine at:\n{self.engine_path}")
            return

        try:
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = subprocess.SW_HIDE

            proc = subprocess.Popen(
                str(self.engine_path),
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=info,
                creationflags=subprocess.CREATE_NO_WINDOW if 'CREATE_NO_WINDOW' in dir(subprocess) else 0
            )

            try:
                stdout, stderr = proc.communicate("uci\n", timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                QMessageBox.warning(
                    self, "Engine Timeout",
                    f"The engine '{self.engine_path.name}' did not respond within 5 seconds.\n"
                    "It may be incompatible, not a valid UCI engine, or require a specific instruction set."
                )
                return

            output = stdout.splitlines()
            
            if not any(line.strip() == "uciok" for line in output):
                QMessageBox.warning(
                    self, "Invalid UCI Engine",
                    f"The engine '{self.engine_path.name}' did not respond with 'uciok'.\n"
                    "Please ensure it is a standard UCI-compliant engine."
                )
                # Still try to parse what we got, might have partial info
            
            for line in output:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("id name"):
                    self.engine_name = line[len("id name"):].strip()
                elif line.startswith("option name"):
                    try:
                        name_part, rest_part = line.split(" type ", 1)
                        name = name_part[len("option name "):].strip()
                        
                        parts = rest_part.split()
                        opt_type = parts[0]
                        
                        rest = parts[1:]
                        default, min_val, max_val = None, None, None
                        variables = []

                        if "default" in rest:
                            default_idx = rest.index("default")
                            
                            end_idx = len(rest)
                            for token in ["min", "var"]:
                                if token in rest[default_idx:]:
                                    try:
                                        end_idx = min(end_idx, rest.index(token, default_idx))
                                    except ValueError:
                                        continue
                            
                            default = " ".join(rest[default_idx + 1 : end_idx])
                            if default == "<empty>": default = ""
                            
                            rem = rest[end_idx:]
                        else:
                            rem = rest

                        if "min" in rem and "max" in rem:
                            min_val = int(rem[rem.index("min") + 1])
                            max_val = int(rem[rem.index("max") + 1])
                        
                        var_values = []
                        for i, token in enumerate(rem):
                            if token == "var":
                                value_tokens = []
                                for j in range(i + 1, len(rem)):
                                    if rem[j] == "var":
                                        break
                                    value_tokens.append(rem[j])
                                if value_tokens:
                                    var_values.append(" ".join(value_tokens))
                        variables = var_values
                        
                        self._engine_options[name] = {
                            'type': opt_type, 'default': default, 'min': min_val,
                            'max': max_val, 'var': variables
                        }

                    except (ValueError, IndexError) as e:
                        print(f"Could not parse UCI option: {line} ({e})", file=os.sys.stderr)
                        continue
        
        except Exception as e:
            QMessageBox.critical(
                self, "Engine Load Error",
                f"An unexpected error occurred while loading the engine:\n\n{e}"
            )
    
    def _setup_ui(self):
        """Build UI dynamically from engine options."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Create scroll area for all options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(400)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(12)
        
        # Separate options into resource vs behavior
        resource_opts = {}
        behavior_opts = {}
        
        for name, opt in self._engine_options.items():
            if name in self.SKIP_OPTIONS:
                continue
            if opt.get('type') == 'button':
                continue
            if name in self.RESOURCE_OPTIONS:
                resource_opts[name] = opt
            else:
                behavior_opts[name] = opt
        
        # Resource Settings Group
        if resource_opts:
            resource_group = QGroupBox("Resource Settings")
            resource_layout = QFormLayout(resource_group)
            resource_layout.setSpacing(8)
            
            for name, opt in sorted(resource_opts.items()):
                widget = self._create_widget_for_option(name, opt)
                if widget:
                    self._option_widgets[name] = widget
                    resource_layout.addRow(f"{name}:", widget)
            
            scroll_layout.addWidget(resource_group)
        
        # Engine Behavior Group
        if behavior_opts:
            behavior_group = QGroupBox("Engine Behavior")
            behavior_layout = QFormLayout(behavior_group)
            behavior_layout.setSpacing(8)
            
            for name, opt in sorted(behavior_opts.items()):
                widget = self._create_widget_for_option(name, opt)
                if widget:
                    self._option_widgets[name] = widget
                    behavior_layout.addRow(f"{name}:", widget)
            
            scroll_layout.addWidget(behavior_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self.setMinimumWidth(450)

    def _create_widget_for_option(self, name: str, opt: dict) -> QWidget | None:
        """Create appropriate widget for UCI option type."""
        opt_type = opt.get('type', 'string')
        default = opt.get('default')
        current = self._current_settings.get(name, default)
        
        if opt_type == 'spin':
            widget = QSpinBox()
            widget.setMinimum(opt.get('min', 0))
            widget.setMaximum(opt.get('max', 999999))
            try:
                widget.setValue(int(current) if current is not None else int(default or 0))
            except (ValueError, TypeError):
                widget.setValue(int(default or 0))
            return widget
            
        elif opt_type == 'check':
            widget = QCheckBox()
            if isinstance(current, bool):
                widget.setChecked(current)
            elif isinstance(current, str):
                widget.setChecked(current.lower() == 'true')
            else:
                widget.setChecked(str(default).lower() == 'true' if default else False)
            return widget
            
        elif opt_type == 'combo':
            widget = QComboBox()
            options = opt.get('var', [])
            widget.addItems(options)
            if current in options:
                widget.setCurrentText(str(current))
            elif default in options:
                widget.setCurrentText(str(default))
            return widget
            
        elif opt_type == 'string':
            widget = QLineEdit()
            widget.setText(str(current) if current else (str(default) if default else ''))
            # Add browse button for path-like options
            if 'path' in name.lower() or 'file' in name.lower():
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(4)
                h_layout.addWidget(widget)
                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(30)
                browse_btn.clicked.connect(lambda checked, w=widget: self._browse_path(w))
                h_layout.addWidget(browse_btn)
                # Store reference to the actual line edit
                container.line_edit = widget
                return container
            return widget
            
        return None
    
    def _browse_path(self, line_edit: QLineEdit):
        """Open directory browser for path options."""
        path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if path:
            line_edit.setText(path)
    
    def _reset_defaults(self):
        """Reset all options to engine defaults."""
        for name, widget in self._option_widgets.items():
            opt = self._engine_options.get(name, {})
            default = opt.get('default')
            
            if isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(default) if default is not None else 0)
                except (ValueError, TypeError):
                    widget.setValue(0)
                    
            elif isinstance(widget, QCheckBox):
                widget.setChecked(str(default).lower() == 'true' if default else False)
                
            elif isinstance(widget, QComboBox):
                if default and default in [widget.itemText(i) for i in range(widget.count())]:
                    widget.setCurrentText(str(default))
                elif widget.count() > 0:
                    widget.setCurrentIndex(0)
                    
            elif isinstance(widget, QLineEdit):
                widget.setText(str(default) if default else '')
                
            elif isinstance(widget, QWidget) and hasattr(widget, 'line_edit'):
                # Container with browse button
                widget.line_edit.setText(str(default) if default else '')
    
    def get_uci_options(self) -> dict:
        """Return dict of option_name -> value for all modified options."""
        result = {}
        
        for name, widget in self._option_widgets.items():
            opt = self._engine_options.get(name, {})
            default = opt.get('default')
            
            if isinstance(widget, QSpinBox):
                value = widget.value()
                # Only include if different from default
                try:
                    if value != int(default or 0):
                        result[name] = value
                except (ValueError, TypeError):
                    if str(value) != str(default):
                        result[name] = value
                    
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
                default_bool = str(default).lower() == 'true' if default else False
                if value != default_bool:
                    result[name] = value
                    
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
                if value != default:
                    result[name] = value
                    
            elif isinstance(widget, QLineEdit):
                value = widget.text().strip()
                if value and value != (default or ''):
                    result[name] = value
                    
            elif isinstance(widget, QWidget) and hasattr(widget, 'line_edit'):
                # Container with browse button
                value = widget.line_edit.text().strip()
                if value and value != (default or ''):
                    result[name] = value
        
        return result
    
    def get_engine_name(self) -> str:
        """Return detected engine name."""
        return self.engine_name