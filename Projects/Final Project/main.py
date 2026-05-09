"""
Smart Warehouse Decision Support System - Main Application Entry Point
"""

import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QStackedWidget,
    QFrame, QMessageBox, QFileDialog, QDialog,
    QFormLayout, QLineEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon
import config

from services.data_service import DataService
from logic.decision_engine import DecisionEngine
from logic.behavior_tracker import BehaviorTracker
from logic.barcode_scanner import BarcodeScanner, BarcodeLookup
from ui.dashboard import Dashboard
from ui.management import ManagementPage, AddProductDialog
from ui.reports import ReportsPage
from ui.settings import SettingsPage
from ui.popup_recommendation import PopupManager
from ui.scan_dialog import ScanActionDialog, UnknownBarcodeDialog


def resource_path(relative_path: str) -> str:
    """
    Resolve resource paths for both dev and PyInstaller builds.
    PyInstaller extracts bundled files into sys._MEIPASS at runtime.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


class LoginDialog(QDialog):
    """Simple database-backed login dialog."""

    def __init__(self, data_service: DataService, parent=None):
        super().__init__(parent)
        self.data_service = data_service
        self.user = None
        self.setWindowTitle("Sign In - SmartDSS v2.0")
        self.setFixedSize(380, 220)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Login to continue")
        title.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #2c3e50; }")
        layout.addWidget(title)

        hint = QLabel("Default accounts: admin/admin123 or viewer/viewer123")
        hint.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
        layout.addWidget(hint)

        form = QFormLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form.addRow("Username:", self.username_input)
        form.addRow("Password:", self.password_input)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("QLabel { color: #e74c3c; font-size: 11px; }")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.attempt_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        user = self.data_service.authenticate_user(username, password)
        if not user:
            self.error_label.setText("Invalid username or password.")
            return
        self.user = user
        self.accept()


class MainWindow(QMainWindow):
    """Main warehouse application window"""
    
    def __init__(self, current_user: dict, data_service: DataService = None):
        super().__init__()
        self.current_user = current_user or {"username": "unknown", "role": "viewer"}
        self.user_role = self.current_user.get("role", "viewer")
        self.is_admin = self.user_role == "admin"

        self.data_service = data_service or DataService()
        self.decision_engine = DecisionEngine(self.data_service)
        self.behavior_tracker = BehaviorTracker(self.data_service)
        self.popup_manager = PopupManager(self.data_service, self.behavior_tracker)
        
        # Barcode scanner setup
        self.barcode_scanner = BarcodeScanner(self)
        self.barcode_scanner.barcode_scanned.connect(self.handle_barcode_scan)
        self.barcode_lookup = BarcodeLookup(self.data_service)
        self.installEventFilter(self)
        
        self.setup_ui()
        
        self.popup_timer = QTimer()
        self.popup_timer.timeout.connect(self.check_for_recommendations)
        self.popup_timer.start(60000)
        
        QTimer.singleShot(5000, self.check_for_recommendations)
    
    def setup_ui(self):
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.setFixedSize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        # Window/taskbar icon (works in dev + bundled exe)
        icon_path = resource_path(os.path.join("assets", "app_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar
        sidebar = QFrame()
        sidebar.setStyleSheet("QFrame { background-color: #2c3e50; }")
        sidebar.setFixedWidth(200)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 30)
        sidebar_layout.setSpacing(10)
        
        app_title = QLabel("📦 Smart WMS")
        app_title.setStyleSheet("QLabel { color: white; font-size: 18px; font-weight: bold; padding-bottom: 20px; }")
        sidebar_layout.addWidget(app_title)

        user_label = QLabel(f"👤 {self.current_user.get('username','user')} ({self.user_role})")
        user_label.setStyleSheet("QLabel { color: #bdc3c7; font-size: 11px; padding-bottom: 10px; }")
        sidebar_layout.addWidget(user_label)
        
        self.dashboard_btn = self.create_nav_button("📊 Dashboard", "dashboard")
        self.dashboard_btn.clicked.connect(lambda: self.show_page("dashboard"))
        sidebar_layout.addWidget(self.dashboard_btn)
        
        self.management_btn = self.create_nav_button("📦 Inventory", "management")
        self.management_btn.clicked.connect(lambda: self.show_page("management"))
        sidebar_layout.addWidget(self.management_btn)
        
        self.reports_btn = self.create_nav_button("📈 Reports", "reports")
        self.reports_btn.clicked.connect(lambda: self.show_page("reports"))
        sidebar_layout.addWidget(self.reports_btn)
        
        self.settings_btn = self.create_nav_button("⚙️ Settings", "settings")
        self.settings_btn.clicked.connect(lambda: self.show_page("settings"))
        sidebar_layout.addWidget(self.settings_btn)

        switch_btn = QPushButton("🔐 Change Account")
        switch_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: none;
                padding: 8px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2c3e50; }
        """)
        switch_btn.clicked.connect(self.change_account)
        sidebar_layout.addWidget(switch_btn)
        
        # Barcode scan toggle
        sidebar_layout.addSpacing(20)
        
        scan_status = QLabel("📷 Barcode Scanner")
        scan_status.setStyleSheet("QLabel { color: #bdc3c7; font-size: 11px; font-weight: bold; }")
        scan_status.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(scan_status)
        
        self.scan_toggle_btn = QPushButton("● Active")
        self.scan_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #219150; }
        """)
        self.scan_toggle_btn.setCheckable(True)
        self.scan_toggle_btn.setChecked(True)
        self.scan_toggle_btn.clicked.connect(self.toggle_scan_mode)
        sidebar_layout.addWidget(self.scan_toggle_btn)
        
        sidebar_layout.addStretch()
        
        version_label = QLabel(f"v{config.APP_VERSION}")
        version_label.setStyleSheet("QLabel { color: #95a5a6; font-size: 11px; }")
        version_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(version_label)
        
        main_layout.addWidget(sidebar)
        
        # Content area
        self.content_area = QStackedWidget()
        self.content_area.setStyleSheet("QStackedWidget { background-color: #ecf0f1; }")
        
        self.dashboard = Dashboard(self.data_service, self.decision_engine, can_execute_actions=self.is_admin)
        self.dashboard.action_requested.connect(self.handle_action_request)
        
        self.management = ManagementPage(
            self.data_service,
            can_edit=self.is_admin,
            current_username=self.current_user.get("username", "system")
        )
        self.management.data_changed.connect(self.refresh_all_pages)
        
        self.reports = ReportsPage(self.data_service, self.decision_engine)
        
        self.settings = SettingsPage(can_edit=self.is_admin)
        self.settings.settings_changed.connect(self.on_settings_changed)
        
        self.content_area.addWidget(self.dashboard)
        self.content_area.addWidget(self.management)
        self.content_area.addWidget(self.reports)
        self.content_area.addWidget(self.settings)
        
        main_layout.addWidget(self.content_area)
        
        self.show_page("dashboard")
    
    def create_nav_button(self, text: str, page_name: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ecf0f1;
                border: none;
                padding: 12px 15px;
                text-align: left;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:pressed { background-color: #1c2833; }
        """)
        btn.setProperty("page", page_name)
        return btn
    
    def show_page(self, page_name: str):
        if page_name in ("management", "settings") and not self.is_admin:
            QMessageBox.information(self, "Access Restricted", "Viewer role has read-only access (Dashboard/Reports).")
            page_name = "dashboard"

        for btn in [self.dashboard_btn, self.management_btn, self.reports_btn, self.settings_btn]:
            if btn.property("page") == page_name:
                btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; padding: 12px 15px; text-align: left; border-radius: 5px; font-size: 13px; font-weight: bold; }")
            else:
                btn.setStyleSheet("QPushButton { background-color: transparent; color: #ecf0f1; border: none; padding: 12px 15px; text-align: left; border-radius: 5px; font-size: 13px; } QPushButton:hover { background-color: #34495e; }")
        
        page_map = {"dashboard": 0, "management": 1, "reports": 2, "settings": 3}
        self.content_area.setCurrentIndex(page_map[page_name])
        
        if page_name == "dashboard":
            self.dashboard.refresh_data()
        elif page_name == "reports":
            self.reports.load_data()
    
    def handle_action_request(self, action_type: str, target_id: int):
        if not self.is_admin:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot execute actions.")
            return
        if action_type == 'restock':
            product = self.data_service.get_product(target_id)
            if not product:
                return
            qty = product.get('reorder_qty', 50)
            from PySide6.QtWidgets import QInputDialog
            qty, ok = QInputDialog.getInt(self, "Restock", f"Reorder quantity for {product['sku']}:", qty, 1, 10000)
            if ok:
                # Create a purchase order suggestion or just record intent
                self.data_service.create_alert(
                    alert_type="restock_action",
                    severity="medium",
                    message=f"Manual reorder initiated: {product['sku']} x{qty}",
                    target_id=target_id,
                    target_type="product"
                )
                QMessageBox.information(self, "Action Recorded", f"Reorder for {product['sku']} x{qty} logged. Create PO in Management.")
                self.refresh_all_pages()
        
        elif action_type == 'clear_expiring':
            product = self.data_service.get_product(target_id)
            if product:
                reply = QMessageBox.question(self, "Clear Expiring", f"Mark {product['sku']} for clearance/discount?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.data_service.create_alert(
                        alert_type="clearance",
                        severity="medium",
                        message=f"Marked for clearance: {product['sku']} expiring {product.get('expiry_date','soon')}",
                        target_id=target_id,
                        target_type="product"
                    )
                    self.refresh_all_pages()
        
        elif action_type == 'clear_dead_stock':
            product = self.data_service.get_product(target_id)
            if product:
                reply = QMessageBox.question(self, "Dead Stock", f"Dispose or return {product['sku']} to supplier?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.data_service.create_alert(
                        alert_type="disposal",
                        severity="medium",
                        message=f"Marked for disposal: {product['sku']} (dead stock)",
                        target_id=target_id,
                        target_type="product"
                    )
                    self.refresh_all_pages()
    
    def eventFilter(self, watched, event):
        """Global event filter to capture barcode scanner input"""
        from PySide6.QtGui import QKeyEvent
        if isinstance(event, QKeyEvent) and event.type() == QKeyEvent.Type.KeyPress:
            if self.barcode_scanner.process_key_event(event):
                return True  # Consumed by barcode scanner
        return super().eventFilter(watched, event)
    
    def handle_barcode_scan(self, barcode: str):
        """Handle a detected barcode scan"""
        # If Add Product dialog is active, route scan directly there.
        active_modal = QApplication.activeModalWidget()
        if isinstance(active_modal, AddProductDialog):
            active_modal.handle_scanned_barcode(barcode)
            self.data_service.record_barcode_scan(
                barcode=barcode,
                action="add_product_fill",
                notes="Scanned while Add Product dialog active"
            )
            return

        product = self.barcode_lookup.find_product_by_barcode(barcode)
        
        if product:
            dialog = ScanActionDialog(barcode, product, self.data_service, self)
            dialog.stock_updated.connect(self.refresh_all_pages)
            dialog.exec()
        else:
            unknown_dialog = UnknownBarcodeDialog(barcode, self)
            unknown_dialog.create_product.connect(self._create_product_from_scan)
            unknown_dialog.exec()
    
    def _create_product_from_scan(self, barcode: str):
        """Create product from unknown barcode scan with rich prefill support"""
        preset = self.data_service.lookup_barcode_metadata(barcode) or {}
        preset["sku"] = barcode
        if not preset.get("name"):
            preset["name"] = f"Item-{barcode[-6:]}" if len(barcode) >= 6 else f"Item-{barcode}"
            preset["category"] = "Uncategorized"
            preset["unit"] = "pcs"

        dialog = AddProductDialog(
            self.data_service,
            self.data_service.get_all_locations(),
            self.data_service.get_all_suppliers(),
            self,
            preset=preset,
        )

        if dialog.exec():
            data = dialog.get_data()
            if data['sku'] and data['name']:
                initial_stock = int(data.pop('initial_stock', 0) or 0)
                pid = self.data_service.add_product(**data)
                if initial_stock > 0:
                    location_id = data.get('location_id') or (self.data_service.get_all_locations()[0]['id'] if self.data_service.get_all_locations() else None)
                    if location_id:
                        self.data_service.set_stock(pid, location_id, initial_stock)
                        self.data_service.record_movement(
                            product_id=pid,
                            movement_type='IN',
                            quantity=initial_stock,
                            location_id=location_id,
                            reference='INITIAL-SCAN',
                            notes='Initial stock from barcode new product flow'
                        )
                QMessageBox.information(self, "Created", f"Product '{data['name']}' created with SKU '{data['sku']}'.")
                self.refresh_all_pages()

                product = self.barcode_lookup.find_product_by_barcode(barcode)
                if product:
                    scan_dialog = ScanActionDialog(barcode, product, self.data_service, self)
                    scan_dialog.stock_updated.connect(self.refresh_all_pages)
                    scan_dialog.exec()
    
    def toggle_scan_mode(self):
        """Toggle barcode scanner on/off"""
        enabled = self.scan_toggle_btn.isChecked()
        self.barcode_scanner.set_enabled(enabled)
        if enabled:
            self.scan_toggle_btn.setText("● Active")
            self.scan_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #219150; }
            """)
        else:
            self.scan_toggle_btn.setText("○ Disabled")
            self.scan_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #7f8c8d; }
            """)
    
    def check_for_recommendations(self):
        top_rec = self.dashboard.get_top_recommendation()
        if top_rec and top_rec['priority_level'] == 'HIGH':
            self.popup_manager.show_recommendation_popup(top_rec, self)
    
    def refresh_all_pages(self):
        self.dashboard.refresh_data()
        self.management.load_data()
        self.reports.load_data()
    
    def on_settings_changed(self):
        import importlib
        importlib.reload(config)
        self.decision_engine.weights = {
            'urgency': config.URGENCY_WEIGHT,
            'frequency': config.FREQUENCY_WEIGHT,
            'impact': config.IMPACT_WEIGHT,
            'recency': config.RECENCY_WEIGHT
        }
        self.refresh_all_pages()
        QMessageBox.information(self, "Settings Applied", "Settings updated successfully.")

    def change_account(self):
        """Log out current user and sign in as another user."""
        login = LoginDialog(self.data_service, self)
        if login.exec() != QDialog.Accepted:
            return
        if (login.user or {}).get("role") == "admin":
            new_window = MainWindow(current_user=login.user, data_service=self.data_service)
        else:
            new_window = ViewerWindow(current_user=login.user, data_service=self.data_service)
        new_window.show()
        self._next_window = new_window
        self.close()


class ViewerWindow(QMainWindow):
    """Viewer-only application window (separate from admin window)."""

    def __init__(self, current_user: dict, data_service: DataService = None):
        super().__init__()
        self.current_user = current_user or {"username": "viewer", "role": "viewer"}
        self.user_role = "viewer"
        self.data_service = data_service or DataService()
        self.decision_engine = DecisionEngine(self.data_service)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"{config.APP_NAME} v{config.APP_VERSION} - Viewer")
        self.setFixedSize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        icon_path = resource_path(os.path.join("assets", "app_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setStyleSheet("QFrame { background-color: #2c3e50; }")
        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 30)
        sidebar_layout.setSpacing(10)

        app_title = QLabel("📦 Smart WMS")
        app_title.setStyleSheet("QLabel { color: white; font-size: 18px; font-weight: bold; padding-bottom: 20px; }")
        sidebar_layout.addWidget(app_title)

        user_label = QLabel(f"👤 {self.current_user.get('username','viewer')} (viewer)")
        user_label.setStyleSheet("QLabel { color: #bdc3c7; font-size: 11px; padding-bottom: 10px; }")
        sidebar_layout.addWidget(user_label)

        self.dashboard_btn = self.create_nav_button("📊 Dashboard", "dashboard")
        self.dashboard_btn.clicked.connect(lambda: self.show_page("dashboard"))
        sidebar_layout.addWidget(self.dashboard_btn)

        self.management_btn = self.create_nav_button("📦 Inventory (Read-Only)", "management")
        self.management_btn.clicked.connect(lambda: self.show_page("management"))
        sidebar_layout.addWidget(self.management_btn)

        self.reports_btn = self.create_nav_button("📈 Reports", "reports")
        self.reports_btn.clicked.connect(lambda: self.show_page("reports"))
        sidebar_layout.addWidget(self.reports_btn)

        switch_btn = QPushButton("🔐 Change Account")
        switch_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: none;
                padding: 8px 10px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2c3e50; }
        """)
        switch_btn.clicked.connect(self.change_account)
        sidebar_layout.addWidget(switch_btn)

        sidebar_layout.addStretch()

        version_label = QLabel(f"v{config.APP_VERSION}")
        version_label.setStyleSheet("QLabel { color: #95a5a6; font-size: 11px; }")
        version_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        self.content_area = QStackedWidget()
        self.content_area.setStyleSheet("QStackedWidget { background-color: #ecf0f1; }")

        # Viewer cannot execute actions or mutate data.
        self.dashboard = Dashboard(self.data_service, self.decision_engine, can_execute_actions=False)
        self.management = ManagementPage(
            self.data_service,
            can_edit=False,
            current_username=self.current_user.get("username", "viewer")
        )
        self.reports = ReportsPage(self.data_service, self.decision_engine)

        self.content_area.addWidget(self.dashboard)
        self.content_area.addWidget(self.management)
        self.content_area.addWidget(self.reports)

        main_layout.addWidget(self.content_area)
        self.show_page("dashboard")

    def create_nav_button(self, text: str, page_name: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ecf0f1;
                border: none;
                padding: 12px 15px;
                text-align: left;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:pressed { background-color: #1c2833; }
        """)
        btn.setProperty("page", page_name)
        return btn

    def show_page(self, page_name: str):
        for btn in [self.dashboard_btn, self.management_btn, self.reports_btn]:
            if btn.property("page") == page_name:
                btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; padding: 12px 15px; text-align: left; border-radius: 5px; font-size: 13px; font-weight: bold; }")
            else:
                btn.setStyleSheet("QPushButton { background-color: transparent; color: #ecf0f1; border: none; padding: 12px 15px; text-align: left; border-radius: 5px; font-size: 13px; } QPushButton:hover { background-color: #34495e; }")

        page_map = {"dashboard": 0, "management": 1, "reports": 2}
        self.content_area.setCurrentIndex(page_map[page_name])

        if page_name == "dashboard":
            self.dashboard.refresh_data()
        elif page_name == "reports":
            self.reports.load_data()

    def change_account(self):
        login = LoginDialog(self.data_service, self)
        if login.exec() != QDialog.Accepted:
            return
        if (login.user or {}).get("role") == "admin":
            new_window = MainWindow(current_user=login.user, data_service=self.data_service)
        else:
            new_window = ViewerWindow(current_user=login.user, data_service=self.data_service)
        new_window.show()
        self._next_window = new_window
        self.close()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    icon_path = resource_path(os.path.join("assets", "app_icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    data_service = DataService()
    login = LoginDialog(data_service)
    if login.exec() != QDialog.Accepted:
        return

    if (login.user or {}).get("role") == "admin":
        window = MainWindow(current_user=login.user, data_service=data_service)
    else:
        window = ViewerWindow(current_user=login.user, data_service=data_service)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
