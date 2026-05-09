"""
Dashboard UI - Warehouse stock priorities and alerts
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from typing import Dict, List, Optional
import utils
import config
from services.data_service import DataService
from logic.decision_engine import DecisionEngine


class PriorityCard(QFrame):
    """A card displaying a warehouse priority action"""
    
    action_clicked = Signal(dict)
    
    def __init__(self, recommendation: Dict, can_execute_actions: bool = True):
        super().__init__()
        self.recommendation = recommendation
        self.can_execute_actions = can_execute_actions
        self.setup_ui()
    
    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedSize(300, 200)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        priority = self.recommendation['priority_level']
        priority_color = utils.get_priority_color(priority)
        
        priority_label = QLabel(f"{priority} PRIORITY")
        priority_label.setStyleSheet(f"""
            QLabel {{
                background-color: {priority_color};
                color: white;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        priority_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(priority_label)
        
        # SKU + Name
        sku_name = f"[{self.recommendation.get('sku', 'N/A')}] {self.recommendation['target_name']}"
        title_label = QLabel(sku_name)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        layout.addWidget(title_label)
        
        # Action type
        action_map = {
            'restock': 'REORDER NOW',
            'clear_expiring': 'CLEAR EXPIRING',
            'clear_dead_stock': 'DISPOSE DEAD STOCK'
        }
        action_label = QLabel(action_map.get(self.recommendation['action_type'], 'ACTION NEEDED'))
        action_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #3498db;
                font-weight: bold;
            }
        """)
        layout.addWidget(action_label)
        
        # Score + Cost
        score = self.recommendation['score']
        est_cost = self.recommendation.get('est_cost', 0)
        score_label = QLabel(f"Score: {score} | Est. Cost: {config.CURRENCY_SYMBOL}{est_cost:.2f}")
        score_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
            }
        """)
        layout.addWidget(score_label)
        
        # Reason
        reason = utils.truncate_text(self.recommendation['reason'], 70)
        reason_label = QLabel(reason)
        reason_label.setWordWrap(True)
        reason_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #95a5a6;
                font-style: italic;
            }
        """)
        layout.addWidget(reason_label)
        
        # Action button
        action_btn = QPushButton("Take Action")
        action_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        action_btn.clicked.connect(lambda: self.action_clicked.emit(self.recommendation))
        action_btn.setEnabled(self.can_execute_actions)
        if not self.can_execute_actions:
            action_btn.setText("View Only")
        layout.addWidget(action_btn)
        
        layout.addStretch()


class AlertCard(QFrame):
    """A card displaying a warehouse alert"""

    resolve_requested = Signal(int)
    
    def __init__(self, alert: Dict, can_resolve: bool = True):
        super().__init__()
        self.alert = alert
        self.can_resolve = can_resolve
        self.setup_ui()
    
    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedHeight(80)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        severity = self.alert['severity']
        severity_color = utils.get_severity_color(severity)
        
        severity_label = QLabel("!")
        severity_label.setFixedSize(30, 30)
        severity_label.setStyleSheet(f"""
            QLabel {{
                background-color: {severity_color};
                color: white;
                border-radius: 15px;
                font-weight: bold;
                font-size: 18px;
            }}
        """)
        severity_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(severity_label)
        
        message_layout = QVBoxLayout()
        message_layout.setSpacing(5)
        
        alert_type = self.alert['alert_type'].replace('_', ' ').title()
        type_label = QLabel(alert_type)
        type_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: bold;
                color: #7f8c8d;
            }
        """)
        message_layout.addWidget(type_label)
        
        message_label = QLabel(self.alert['message'])
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #2c3e50;
            }
        """)
        message_layout.addWidget(message_label)
        
        layout.addLayout(message_layout)
        layout.addStretch()

        resolve_btn = QPushButton("Resolve")
        resolve_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 6px 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #219150; }
        """)
        resolve_btn.clicked.connect(lambda: self.resolve_requested.emit(self.alert['id']))
        resolve_btn.setEnabled(self.can_resolve)
        if not self.can_resolve:
            resolve_btn.setText("Locked")
        layout.addWidget(resolve_btn)


class Dashboard(QWidget):
    """Main warehouse dashboard"""
    
    action_requested = Signal(str, int)
    refresh_requested = Signal()
    
    def __init__(self, data_service: DataService, decision_engine: DecisionEngine, can_execute_actions: bool = True):
        super().__init__()
        self.data_service = data_service
        self.decision_engine = decision_engine
        self.can_execute_actions = can_execute_actions
        self.last_popup_time = None
        self.setup_ui()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Header
        header = QLabel("📦 Warehouse Decision Dashboard")
        header.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        main_layout.addWidget(header)
        
        subtitle = QLabel("Prioritized stock actions based on levels, expiry, and movement patterns")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
            }
        """)
        main_layout.addWidget(subtitle)
        
        # Alerts section
        alerts_label = QLabel("🚨 Active Alerts")
        alerts_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #e74c3c;
            }
        """)
        main_layout.addWidget(alerts_label)
        
        self.alerts_scroll = QScrollArea()
        self.alerts_scroll.setWidgetResizable(True)
        self.alerts_scroll.setFixedHeight(120)
        self.alerts_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.alerts_container = QWidget()
        self.alerts_layout = QVBoxLayout(self.alerts_container)
        self.alerts_layout.setSpacing(10)
        self.alerts_layout.addStretch()
        
        self.alerts_scroll.setWidget(self.alerts_container)
        main_layout.addWidget(self.alerts_scroll)
        
        # Recommendations section
        recs_label = QLabel("⚡ Recommended Stock Actions")
        recs_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        main_layout.addWidget(recs_label)
        
        self.recs_scroll = QScrollArea()
        self.recs_scroll.setWidgetResizable(True)
        self.recs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.recs_container = QWidget()
        self.recs_layout = QGridLayout(self.recs_container)
        self.recs_layout.setSpacing(15)
        
        self.recs_scroll.setWidget(self.recs_container)
        main_layout.addWidget(self.recs_scroll)
        
        # Quick actions bar
        quick_layout = QHBoxLayout()
        
        self.po_btn = QPushButton("📋 Generate Purchase Plan")
        self.po_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.po_btn.clicked.connect(self.show_purchase_plan)
        quick_layout.addWidget(self.po_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_data)
        quick_layout.addWidget(refresh_btn)
        quick_layout.addStretch()
        
        main_layout.addLayout(quick_layout)
        
        self.refresh_data()
    
    def refresh_data(self):
        self.clear_alerts()
        self.clear_recommendations()
        
        alerts = self.data_service.get_active_alerts()
        for alert in alerts[:5]:
            alert_card = AlertCard(alert, can_resolve=self.can_execute_actions)
            alert_card.resolve_requested.connect(self.resolve_alert)
            self.alerts_layout.insertWidget(self.alerts_layout.count() - 1, alert_card)
        
        if not alerts:
            no_alerts = QLabel("No active warehouse alerts")
            no_alerts.setStyleSheet("QLabel { color: #95a5a6; font-style: italic; }")
            self.alerts_layout.insertWidget(self.alerts_layout.count() - 1, no_alerts)
        
        recommendations = self.decision_engine.get_all_recommendations(limit=8)
        
        for i, rec in enumerate(recommendations):
            card = PriorityCard(rec, can_execute_actions=self.can_execute_actions)
            card.action_clicked.connect(self.on_action_clicked)
            row = i // 3
            col = i % 3
            self.recs_layout.addWidget(card, row, col)
        
        if not recommendations:
            no_rec = QLabel("No urgent warehouse actions needed")
            no_rec.setStyleSheet("QLabel { color: #27ae60; font-size: 16px; font-weight: bold; }")
            no_rec.setAlignment(Qt.AlignCenter)
            self.recs_layout.addWidget(no_rec, 0, 0, 1, 3)

    def resolve_alert(self, alert_id: int):
        self.data_service.resolve_alert(alert_id)
        self.refresh_data()
    
    def clear_alerts(self):
        while self.alerts_layout.count() > 1:
            item = self.alerts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def clear_recommendations(self):
        while self.recs_layout.count():
            item = self.recs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def on_action_clicked(self, recommendation: Dict):
        self.action_requested.emit(
            recommendation['action_type'],
            recommendation['target_id']
        )
    
    def show_purchase_plan(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QDialogButtonBox, QMessageBox
        
        plan = self.decision_engine.generate_purchase_plan()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Suggested Purchase Plan")
        dialog.setFixedSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        total_cost = sum(item['line_total'] for item in plan)
        header = QLabel(f"Below Reorder: {len(plan)} products | Total Cost: {config.CURRENCY_SYMBOL}{total_cost:.2f}")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)
        
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["SKU", "Product", "Current", "Suggested Qty", "Unit Cost", "Line Total"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(plan))
        
        for row, item in enumerate(plan):
            table.setItem(row, 0, QTableWidgetItem(item['sku']))
            table.setItem(row, 1, QTableWidgetItem(item['name']))
            table.setItem(row, 2, QTableWidgetItem(str(item['current_stock'])))
            table.setItem(row, 3, QTableWidgetItem(str(item['suggested_qty'])))
            table.setItem(row, 4, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{item['unit_cost']:.2f}"))
            table.setItem(row, 5, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{item['line_total']:.2f}"))
        
        layout.addWidget(table)

        # Actions
        action_row = QHBoxLayout()

        create_po_btn = QPushButton("🧾 Create Draft PO(s)")
        create_po_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #219150; }
        """)

        def _create_pos():
            if not plan:
                QMessageBox.information(dialog, "No Plan", "No purchase plan items to create POs from.")
                return

            # Group by supplier_id
            grouped = {}
            missing = 0
            for item in plan:
                sid = item.get('supplier_id')
                if not sid:
                    missing += 1
                    continue
                grouped.setdefault(sid, []).append(item)

            if not grouped:
                QMessageBox.warning(
                    dialog,
                    "No Suppliers",
                    "None of the plan items have suppliers assigned.\nAssign suppliers to products first (Management → Products)."
                )
                return

            created = []
            for supplier_id, items in grouped.items():
                po_id = self.data_service.create_purchase_order(supplier_id=supplier_id, expected_date=None)
                for it in items:
                    self.data_service.add_po_line(
                        po_id=po_id,
                        product_id=it['product_id'],
                        quantity=int(it.get('suggested_qty') or 0),
                        unit_cost=float(it.get('unit_cost') or 0.0)
                    )
                created.append(po_id)

            msg = f"Created draft PO(s): {', '.join([f'PO-{pid}' for pid in created])}"
            if missing:
                msg += f"\n\nNote: {missing} item(s) were skipped (no supplier assigned)."
            QMessageBox.information(dialog, "Draft POs Created", msg)

        create_po_btn.clicked.connect(_create_pos)
        action_row.addWidget(create_po_btn)
        action_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        action_row.addWidget(buttons)
        layout.addLayout(action_row)
        
        dialog.exec()
    
    def get_top_recommendation(self) -> Optional[Dict]:
        return self.decision_engine.get_top_recommendation()
