"""UCI Engine Configuration Dialog - Bulletproof Edition."""

import sys
import subprocess
from pathlib import Path
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QSpinBox, QCheckBox, QLineEdit, QComboBox, QPushButton,
    QFormLayout, QFileDialog, QScrollArea, QWidget, QMessageBox
)
from PyQt6.QtCore import Qt


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
            QMessageBox.warning(
                self, 
                "Engine Not Found", 
                f"Could not find engine at:\n{self.engine_path}"
            )
            return

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            creationflags = 0
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                str(self.engine_path),
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags
            )

            try:
                stdout, stderr = proc.communicate("uci\n", timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()  # Clean up
                QMessageBox.warning(
                    self, 
                    "Engine Timeout",
                    f"The engine '{self.engine_path.name}' did not respond within 5 seconds.\n\n"
                    "Possible causes:\n"
                    "• Not a UCI-compliant engine (might be WinBoard/XBoard)\n"
                    "• Incompatible CPU instruction set (AVX2/AVX-512)\n"
                    "• Engine requires additional files or configuration\n\n"
                    "The engine may still work with default settings."
                )
                return

            output = stdout.splitlines()
            
            # Check for uciok response
            if not any(line.strip() == "uciok" for line in output):
                QMessageBox.warning(
                    self, 
                    "Invalid UCI Engine",
                    f"The engine '{self.engine_path.name}' did not respond with 'uciok'.\n\n"
                    "Please ensure it is a standard UCI-compliant engine.\n\n"
                    "The engine may still work with default settings."
                )
                # Continue anyway - try to parse what we got
            
            # Parse engine output
            for line in output:
                line = line.strip()
                if not line:
                    continue

                # Get engine name
                if line.startswith("id name"):
                    self.engine_name = line[len("id name"):].strip()
                    continue
                
                # Parse options
                if line.startswith("option name"):
                    self._parse_option_line(line)
        
        except FileNotFoundError:
            QMessageBox.critical(
                self, 
                "Engine Not Found",
                f"Could not execute engine:\n{self.engine_path}\n\n"
                "The file may be missing or not executable."
            )
        except PermissionError:
            QMessageBox.critical(
                self, 
                "Permission Denied",
                f"Cannot execute engine:\n{self.engine_path}\n\n"
                "Check file permissions."
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Engine Load Error",
                f"Unexpected error loading engine:\n\n{type(e).__name__}: {e}"
            )

    def _parse_option_line(self, line: str) -> None:
        """Parse a single UCI option line with maximum fault tolerance."""
        try:
            # Basic structure: "option name <name> type <type> [default <val>] [min <val>] [max <val>] [var <val>]*"
            if " type " not in line:
                return
                
            name_part, rest_part = line.split(" type ", 1)
            name = name_part[len("option name "):].strip()
            
            if not name:
                return
            
            parts = rest_part.split()
            if not parts:
                return
                
            opt_type = parts[0].lower()
            
            # Skip button type options
            if opt_type == 'button':
                return
            
            # Initialize option dict
            option = {
                'type': opt_type,
                'default': None,
                'min': None,
                'max': None,
                'var': []
            }
            
            # Parse tokens
            tokens = parts[1:]
            i = 0
            while i < len(tokens):
                token = tokens[i].lower()
                
                if token == 'default' and i + 1 < len(tokens):
                    # Collect default value (may be multi-word for strings)
                    default_parts = []
                    i += 1
                    while i < len(tokens) and tokens[i].lower() not in ('min', 'max', 'var'):
                        default_parts.append(tokens[i])
                        i += 1
                    option['default'] = ' '.join(default_parts) if default_parts else None
                    if option['default'] == '<empty>':
                        option['default'] = ''
                    continue
                    
                elif token == 'min' and i + 1 < len(tokens):
                    try:
                        option['min'] = int(tokens[i + 1])
                    except ValueError:
                        pass
                    i += 2
                    continue
                    
                elif token == 'max' and i + 1 < len(tokens):
                    try:
                        option['max'] = int(tokens[i + 1])
                    except ValueError:
                        pass
                    i += 2
                    continue
                    
                elif token == 'var' and i + 1 < len(tokens):
                    # Collect var value (may be multi-word)
                    var_parts = []
                    i += 1
                    while i < len(tokens) and tokens[i].lower() != 'var':
                        var_parts.append(tokens[i])
                        i += 1
                    if var_parts:
                        option['var'].append(' '.join(var_parts))
                    continue
                
                i += 1
            
            self._engine_options[name] = option
            
        except Exception as e:
            print(f"[UCI Parse Warning] Could not parse: {line[:80]}... ({e})", file=sys.stderr)
    
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
        
        # Show message if no options found
        if not resource_opts and not behavior_opts:
            from PyQt6.QtWidgets import QLabel
            no_opts_label = QLabel(
                "No configurable options found.\n\n"
                "This engine may:\n"
                "• Not report UCI options\n"
                "• Use non-standard UCI format\n"
                "• Work fine with default settings"
            )
            no_opts_label.setWordWrap(True)
            scroll_layout.addWidget(no_opts_label)
        
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
        """Create appropriate widget for UCI option type - bulletproof version."""
        opt_type = opt.get('type', 'string')
        default = opt.get('default')
        current = self._current_settings.get(name, default)
        
        if opt_type == 'spin':
            widget = QSpinBox()
            
            # Safely extract min/max with bulletproof fallbacks
            min_val = opt.get('min')
            max_val = opt.get('max')
            
            # Handle None, missing, or invalid values
            try:
                min_val = int(min_val) if min_val is not None else -999999
            except (ValueError, TypeError):
                min_val = -999999
                
            try:
                max_val = int(max_val) if max_val is not None else 999999
            except (ValueError, TypeError):
                max_val = 999999
            
            # Sanity check: ensure min <= max
            if min_val > max_val:
                min_val, max_val = -999999, 999999
            
            widget.setMinimum(min_val)
            widget.setMaximum(max_val)
            
            # Determine value to display (priority: current setting > default > 0)
            value_to_set = 0
            for candidate in (current, default, 0):
                try:
                    value_to_set = int(candidate) if candidate is not None else 0
                    break
                except (ValueError, TypeError):
                    continue
            
            # Clamp to valid range
            value_to_set = max(min_val, min(max_val, value_to_set))
            widget.setValue(value_to_set)
            
            return widget
            
        elif opt_type == 'check':
            widget = QCheckBox()
            # Handle various boolean representations
            if isinstance(current, bool):
                widget.setChecked(current)
            elif isinstance(current, str):
                widget.setChecked(current.lower() in ('true', '1', 'yes', 'on'))
            elif isinstance(default, str):
                widget.setChecked(default.lower() in ('true', '1', 'yes', 'on'))
            else:
                widget.setChecked(bool(default) if default else False)
            return widget
            
        elif opt_type == 'combo':
            widget = QComboBox()
            options = opt.get('var', [])
            if options:
                widget.addItems(options)
                if current and str(current) in options:
                    widget.setCurrentText(str(current))
                elif default and str(default) in options:
                    widget.setCurrentText(str(default))
            return widget
            
        elif opt_type == 'string':
            widget = QLineEdit()
            widget.setText(str(current) if current else (str(default) if default else ''))
            
            # Add browse button for path-like options
            if 'path' in name.lower() or 'file' in name.lower() or 'directory' in name.lower():
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
                    val = int(default) if default is not None else 0
                    val = max(widget.minimum(), min(widget.maximum(), val))
                    widget.setValue(val)
                except (ValueError, TypeError):
                    widget.setValue(0)
                    
            elif isinstance(widget, QCheckBox):
                if isinstance(default, str):
                    widget.setChecked(default.lower() in ('true', '1', 'yes', 'on'))
                else:
                    widget.setChecked(bool(default) if default else False)
                
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
                try:
                    default_int = int(default) if default is not None else 0
                    if value != default_int:
                        result[name] = value
                except (ValueError, TypeError):
                    result[name] = value
                    
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
                if isinstance(default, str):
                    default_bool = default.lower() in ('true', '1', 'yes', 'on')
                else:
                    default_bool = bool(default) if default else False
                if value != default_bool:
                    result[name] = value
                    
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
                if value and value != default:
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