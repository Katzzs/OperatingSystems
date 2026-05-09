"""
Popup Recommendation System - Real-time warehouse recommendations
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from typing import Optional, Dict
import utils
import config
from datetime import datetime


class RecommendationPopup(QDialog):
    action_accepted = Signal(dict)
    action_ignored = Signal(dict)
    
    def __init__(self, recommendation: Dict, parent=None):
        super().__init__(parent)
        self.recommendation = recommendation
        self.setup_ui()
        
        self.close_timer = QTimer()
        self.close_timer.timeout.connect(self.on_ignore)
        self.close_timer.start(30000)
    
    def setup_ui(self):
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setFixedSize(420, 280)
        
        container = QFrame()
        container.setStyleSheet("QFrame { background-color: white; border: 2px solid #3498db; border-radius: 10px; }")
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        header_layout = QHBoxLayout()
        
        priority = self.recommendation['priority_level']
        priority_color = utils.get_priority_color(priority)
        
        priority_badge = QLabel(f"{priority}")
        priority_badge.setStyleSheet(f"QLabel {{ background-color: {priority_color}; color: white; padding: 5px 15px; border-radius: 4px; font-weight: bold; font-size: 12px; }}")
        header_layout.addWidget(priority_badge)
        header_layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(25, 25)
        close_btn.setStyleSheet("QPushButton { background-color: transparent; border: none; font-size: 16px; color: #95a5a6; } QPushButton:hover { color: #e74c3c; }")
        close_btn.clicked.connect(self.on_ignore)
        header_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        
        sku = self.recommendation.get('sku', 'N/A')
        action_map = {
            'restock': 'REORDER NOW',
            'clear_expiring': 'CLEAR EXPIRING STOCK',
            'clear_dead_stock': 'DISPOSE DEAD STOCK'
        }
        action_text = action_map.get(self.recommendation['action_type'], 'ACTION NEEDED')
        
        title_label = QLabel(f"{action_text}: [{sku}]")
        title_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #2c3e50; }")
        layout.addWidget(title_label)
        
        target_label = QLabel(self.recommendation['target_name'])
        target_label.setStyleSheet("QLabel { font-size: 14px; color: #34495e; font-weight: bold; }")
        layout.addWidget(target_label)
        
        score = self.recommendation['score']
        est_cost = self.recommendation.get('est_cost', 0)
        score_layout = QHBoxLayout()
        score_label = QLabel(f"Priority Score: {score} | Est. Cost: {config.CURRENCY_SYMBOL}{est_cost:.2f}")
        score_label.setStyleSheet("QLabel { font-size: 12px; color: #7f8c8d; }")
        score_layout.addWidget(score_label)
        
        score_bar = QProgressBar()
        score_bar.setFixedHeight(8)
        score_bar.setRange(0, 100)
        score_bar.setValue(int(score))
        score_bar.setTextVisible(False)
        score_bar.setStyleSheet(f"QProgressBar {{ background-color: #ecf0f1; border-radius: 4px; }} QProgressBar::chunk {{ background-color: {priority_color}; border-radius: 4px; }}")
        score_layout.addWidget(score_bar)
        layout.addLayout(score_layout)
        
        reason_label = QLabel(self.recommendation['reason'])
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet("QLabel { font-size: 12px; color: #7f8c8d; font-style: italic; padding: 8px; background-color: #f8f9fa; border-radius: 5px; }")
        layout.addWidget(reason_label)
        
        button_layout = QHBoxLayout()
        
        execute_btn = QPushButton("✓ Execute Action")
        execute_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; font-size: 13px; } QPushButton:hover { background-color: #219150; } QPushButton:pressed { background-color: #1e8449; }")
        execute_btn.clicked.connect(self.on_execute)
        button_layout.addWidget(execute_btn)
        
        ignore_btn = QPushButton("✕ Ignore")
        ignore_btn.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; font-size: 13px; } QPushButton:hover { background-color: #7f8c8d; } QPushButton:pressed { background-color: #6c7a7d; }")
        ignore_btn.clicked.connect(self.on_ignore)
        button_layout.addWidget(ignore_btn)
        
        layout.addLayout(button_layout)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)
    
    def on_execute(self):
        self.close_timer.stop()
        self.action_accepted.emit(self.recommendation)
        self.accept()
    
    def on_ignore(self):
        self.close_timer.stop()
        self.action_ignored.emit(self.recommendation)
        self.reject()
    
    def show_popup(self, parent_widget):
        if parent_widget:
            geo = parent_widget.geometry()
            x = geo.width() - self.width() - 20
            y = 20
            self.move(parent_widget.mapToGlobal(x, y))
        self.show()


class TradeOffWarningDialog(QDialog):
    def __init__(self, warnings: list, parent=None):
        super().__init__(parent)
        self.warnings = warnings
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("⚠️ Trade-Off Analysis")
        self.setFixedSize(450, 200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Consider the following trade-offs:")
        title.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #e67e22; }")
        layout.addWidget(title)
        
        for warning in self.warnings:
            warning_label = QLabel(warning)
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet("QLabel { font-size: 13px; color: #2c3e50; padding: 8px; background-color: #fef5e7; border-radius: 4px; }")
            layout.addWidget(warning_label)
        
        acknowledge_btn = QPushButton("I Understand")
        acknowledge_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold; }")
        acknowledge_btn.clicked.connect(self.accept)
        layout.addWidget(acknowledge_btn)


class PopupManager:
    def __init__(self, data_service, behavior_tracker):
        self.data_service = data_service
        self.behavior_tracker = behavior_tracker
        self.last_popup_time = None
        self.current_popup = None
    
    def should_show_popup(self, recommendation: Dict) -> bool:
        import config

        if not getattr(config, "ENABLE_POPUPS", True):
            return False
        
        if self.last_popup_time:
            time_since = (datetime.now() - self.last_popup_time).total_seconds()
            if time_since < config.POPUP_COOLDOWN_SECONDS:
                return False
        
        if recommendation['confidence'] < config.MIN_CONFIDENCE_THRESHOLD:
            return False
        
        action_type = recommendation['action_type']
        if not self.behavior_tracker.should_show_popup(action_type, self.last_popup_time):
            return False
        
        return True
    
    def show_recommendation_popup(self, recommendation: Dict, parent_widget) -> bool:
        if not self.should_show_popup(recommendation):
            return False
        
        self.current_popup = RecommendationPopup(recommendation, parent_widget)
        self.current_popup.action_accepted.connect(self.on_popup_accepted)
        self.current_popup.action_ignored.connect(self.on_popup_ignored)
        
        self.current_popup.show_popup(parent_widget)
        self.last_popup_time = datetime.now()
        return True
    
    def on_popup_accepted(self, recommendation: Dict):
        rec_id = self.data_service.save_recommendation(
            action_type=recommendation['action_type'],
            target_id=recommendation['target_id'],
            target_type=recommendation['target_type'],
            score=recommendation['score'],
            priority_level=recommendation['priority_level'],
            reason=recommendation['reason'],
            confidence=recommendation['confidence'],
            executed=True
        )
        self.behavior_tracker.record_action(
            action_type=recommendation['action_type'],
            recommendation_id=rec_id,
            accepted=True,
            context={'target_id': recommendation['target_id']}
        )
    
    def on_popup_ignored(self, recommendation: Dict):
        self.behavior_tracker.record_action(
            action_type=recommendation['action_type'],
            recommendation_id=None,
            accepted=False,
            context={'target_id': recommendation['target_id']}
        )
    
    def show_trade_off_warnings(self, warnings: list, parent_widget):
        if warnings:
            dialog = TradeOffWarningDialog(warnings, parent_widget)
            dialog.exec()
