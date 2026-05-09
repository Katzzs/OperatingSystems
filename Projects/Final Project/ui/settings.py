"""
Settings UI - Application settings and configuration
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSpinBox, QDoubleSpinBox, QFormLayout, QPushButton,
    QMessageBox, QGroupBox, QCheckBox
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
import config


class SettingsPage(QWidget):
    """Settings page for application configuration"""
    
    settings_changed = Signal()
    
    def __init__(self, can_edit: bool = True):
        super().__init__()
        self.can_edit = can_edit
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        """Setup the settings UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = QLabel("⚙️ Warehouse Settings")
        header.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        main_layout.addWidget(header)
        
        # Decision Engine Settings
        engine_group = QGroupBox("Decision Engine Weights")
        engine_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        engine_layout = QFormLayout()
        
        self.urgency_weight = QDoubleSpinBox()
        self.urgency_weight.setRange(0.0, 1.0)
        self.urgency_weight.setSingleStep(0.05)
        self.urgency_weight.setDecimals(2)
        engine_layout.addRow("Urgency Weight:", self.urgency_weight)
        
        self.frequency_weight = QDoubleSpinBox()
        self.frequency_weight.setRange(0.0, 1.0)
        self.frequency_weight.setSingleStep(0.05)
        self.frequency_weight.setDecimals(2)
        engine_layout.addRow("Frequency Weight:", self.frequency_weight)
        
        self.impact_weight = QDoubleSpinBox()
        self.impact_weight.setRange(0.0, 1.0)
        self.impact_weight.setSingleStep(0.05)
        self.impact_weight.setDecimals(2)
        engine_layout.addRow("Impact Weight:", self.impact_weight)
        
        self.recency_weight = QDoubleSpinBox()
        self.recency_weight.setRange(0.0, 1.0)
        self.recency_weight.setSingleStep(0.05)
        self.recency_weight.setDecimals(2)
        engine_layout.addRow("Recency Weight:", self.recency_weight)
        
        engine_group.setLayout(engine_layout)
        main_layout.addWidget(engine_group)
        
        # Priority Thresholds
        threshold_group = QGroupBox("Priority Thresholds")
        threshold_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        threshold_layout = QFormLayout()
        
        self.high_threshold = QSpinBox()
        self.high_threshold.setRange(50, 100)
        self.high_threshold.setValue(config.HIGH_PRIORITY_THRESHOLD)
        threshold_layout.addRow("High Priority Threshold:", self.high_threshold)
        
        self.medium_threshold = QSpinBox()
        self.medium_threshold.setRange(20, 80)
        self.medium_threshold.setValue(config.MEDIUM_PRIORITY_THRESHOLD)
        threshold_layout.addRow("Medium Priority Threshold:", self.medium_threshold)
        
        threshold_group.setLayout(threshold_layout)
        main_layout.addWidget(threshold_group)
        
        # Popup Settings
        popup_group = QGroupBox("Popup Recommendations")
        popup_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        popup_layout = QFormLayout()
        
        self.popup_cooldown = QSpinBox()
        self.popup_cooldown.setRange(10, 300)
        self.popup_cooldown.setValue(config.POPUP_COOLDOWN_SECONDS)
        popup_layout.addRow("Popup Cooldown (seconds):", self.popup_cooldown)
        
        self.min_confidence = QDoubleSpinBox()
        self.min_confidence.setRange(0.0, 1.0)
        self.min_confidence.setSingleStep(0.1)
        self.min_confidence.setDecimals(1)
        self.min_confidence.setValue(config.MIN_CONFIDENCE_THRESHOLD)
        popup_layout.addRow("Min Confidence Threshold:", self.min_confidence)
        
        self.enable_popups = QCheckBox("Enable Popup Recommendations")
        self.enable_popups.setChecked(getattr(config, "ENABLE_POPUPS", True))
        popup_layout.addRow(self.enable_popups)
        
        popup_group.setLayout(popup_layout)
        main_layout.addWidget(popup_group)
        
        # Save button
        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #219150;
            }
        """)
        self.save_btn.clicked.connect(self.save_settings)
        main_layout.addWidget(self.save_btn)

        if not self.can_edit:
            for w in [
                self.urgency_weight, self.frequency_weight, self.impact_weight, self.recency_weight,
                self.high_threshold, self.medium_threshold, self.popup_cooldown, self.min_confidence,
                self.enable_popups
            ]:
                w.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.save_btn.setText("🔒 Admin Only")
        
        main_layout.addStretch()
    
    def load_current_settings(self):
        """Load current settings from config"""
        self.urgency_weight.setValue(config.URGENCY_WEIGHT)
        self.frequency_weight.setValue(config.FREQUENCY_WEIGHT)
        self.impact_weight.setValue(config.IMPACT_WEIGHT)
        self.recency_weight.setValue(config.RECENCY_WEIGHT)
        self.high_threshold.setValue(config.HIGH_PRIORITY_THRESHOLD)
        self.medium_threshold.setValue(config.MEDIUM_PRIORITY_THRESHOLD)
        self.popup_cooldown.setValue(config.POPUP_COOLDOWN_SECONDS)
        self.min_confidence.setValue(config.MIN_CONFIDENCE_THRESHOLD)
        self.enable_popups.setChecked(getattr(config, "ENABLE_POPUPS", True))
    
    def save_settings(self):
        """Save settings to config file"""
        # Validate weights sum to approximately 1.0
        total_weight = (
            self.urgency_weight.value() +
            self.frequency_weight.value() +
            self.impact_weight.value() +
            self.recency_weight.value()
        )
        
        if abs(total_weight - 1.0) > 0.1:
            QMessageBox.warning(
                self, "Invalid Weights",
                f"Weights must sum to approximately 1.0 (current: {total_weight:.2f})"
            )
            return
        
        # Update config file
        config_content = f'''"""
Configuration settings for Smart Decision Support System
"""

import os
import sys
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database settings
DB_NAME = "dss_database.db"
if getattr(sys, "frozen", False):
    APP_DATA_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / "SmartDSS"
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = APP_DATA_DIR / DB_NAME
else:
    DB_PATH = BASE_DIR / DB_NAME

# Application settings
APP_NAME = "Smart Decision Support System"
APP_VERSION = "2.0.0"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
CURRENCY_SYMBOL = "₱"

# Decision Engine settings
URGENCY_WEIGHT = {self.urgency_weight.value()}
FREQUENCY_WEIGHT = {self.frequency_weight.value()}
IMPACT_WEIGHT = {self.impact_weight.value()}
RECENCY_WEIGHT = {self.recency_weight.value()}

# Priority thresholds
HIGH_PRIORITY_THRESHOLD = {self.high_threshold.value()}
MEDIUM_PRIORITY_THRESHOLD = {self.medium_threshold.value()}

# Popup settings
POPUP_COOLDOWN_SECONDS = {self.popup_cooldown.value()}
MIN_CONFIDENCE_THRESHOLD = {self.min_confidence.value()}
ENABLE_POPUPS = {str(bool(self.enable_popups.isChecked()))}
'''
        
        try:
            with open(config.__file__, 'w') as f:
                f.write(config_content)
            
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.settings_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
