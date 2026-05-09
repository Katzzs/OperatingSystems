"""
Management UI - Products, Locations, Stock Movements, Suppliers
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QDialog,
    QMessageBox, QFormLayout, QDialogButtonBox, QDateEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from services.data_service import DataService
from datetime import datetime
from PySide6.QtWidgets import QFileDialog
import config


class AddProductDialog(QDialog):
    def __init__(self, data_service: DataService, locations, suppliers, parent=None, preset=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Product")
        self.setFixedSize(500, 520)
        self.data_service = data_service
        self.locations = locations
        self.suppliers = suppliers
        self.preset = preset or {}
        self.setup_ui()
        self.apply_preset(self.preset)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("SKU-001")
        self.sku_input.editingFinished.connect(self.auto_fill_from_barcode)
        form.addRow("SKU:", self.sku_input)

        scan_lookup_row = QHBoxLayout()
        self.scan_btn = QPushButton("Scan Barcode")
        self.scan_btn.clicked.connect(self.prepare_for_scan)
        scan_lookup_row.addWidget(self.scan_btn)

        self.lookup_btn = QPushButton("Lookup Barcode Details")
        self.lookup_btn.clicked.connect(self.auto_fill_from_barcode)
        scan_lookup_row.addWidget(self.lookup_btn)
        form.addRow("", scan_lookup_row)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Product name")
        form.addRow("Name:", self.name_input)
        
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("e.g., Electronics")
        form.addRow("Category:", self.category_input)
        
        self.unit_input = QLineEdit()
        self.unit_input.setText("pcs")
        form.addRow("Unit:", self.unit_input)
        
        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 999999)
        self.cost_input.setDecimals(2)
        form.addRow(f"Unit Cost ({config.CURRENCY_SYMBOL}):", self.cost_input)
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setDecimals(2)
        form.addRow(f"Unit Price ({config.CURRENCY_SYMBOL}):", self.price_input)
        
        self.reorder_point = QSpinBox()
        self.reorder_point.setRange(0, 10000)
        self.reorder_point.setValue(20)
        form.addRow("Reorder Point:", self.reorder_point)
        
        self.reorder_qty = QSpinBox()
        self.reorder_qty.setRange(1, 10000)
        self.reorder_qty.setValue(50)
        form.addRow("Reorder Qty:", self.reorder_qty)
        
        self.max_stock = QSpinBox()
        self.max_stock.setRange(1, 100000)
        self.max_stock.setValue(200)
        form.addRow("Max Stock:", self.max_stock)
        
        self.location_combo = QComboBox()
        self.location_combo.addItem("None", None)
        for loc in self.locations:
            label = f"{loc['zone']}-{loc['aisle']}-{loc['rack']}-{loc['bin']}"
            self.location_combo.addItem(label, loc['id'])
        if len(self.locations) > 0:
            self.location_combo.setCurrentIndex(1)
        form.addRow("Default Location:", self.location_combo)
        
        self.supplier_combo = QComboBox()
        self.supplier_combo.addItem("None", None)
        for sup in self.suppliers:
            self.supplier_combo.addItem(sup['name'], sup['id'])
        if len(self.suppliers) > 0:
            self.supplier_combo.setCurrentIndex(1)
        form.addRow("Supplier:", self.supplier_combo)
        
        self.initial_stock = QSpinBox()
        self.initial_stock.setRange(0, 100000)
        self.initial_stock.setValue(0)
        form.addRow("Initial Stock:", self.initial_stock)
        
        self.expiry_input = QLineEdit()
        self.expiry_input.setPlaceholderText("YYYY-MM-DD (optional)")
        form.addRow("Expiry Date:", self.expiry_input)

        self.lookup_status = QLabel("")
        self.lookup_status.setWordWrap(True)
        self.lookup_status.setStyleSheet("QLabel { color: #7f8c8d; font-size: 11px; }")
        form.addRow("Barcode Status:", self.lookup_status)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_combo_value(self, combo: QComboBox, target):
        if target is None:
            return
        idx = combo.findData(target)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def apply_preset(self, preset: dict):
        if not preset:
            return
        self.sku_input.setText(str(preset.get("sku", "") or self.sku_input.text()))
        if preset.get("name"):
            self.name_input.setText(str(preset["name"]))
        if preset.get("category"):
            self.category_input.setText(str(preset["category"]))
        if preset.get("unit"):
            self.unit_input.setText(str(preset["unit"]))
        if preset.get("unit_cost") is not None:
            self.cost_input.setValue(float(preset.get("unit_cost") or 0.0))
        if preset.get("unit_price") is not None:
            self.price_input.setValue(float(preset.get("unit_price") or 0.0))
        if preset.get("reorder_point") is not None:
            self.reorder_point.setValue(int(preset.get("reorder_point") or 20))
        if preset.get("reorder_qty") is not None:
            self.reorder_qty.setValue(int(preset.get("reorder_qty") or 50))
        if preset.get("max_stock") is not None:
            self.max_stock.setValue(int(preset.get("max_stock") or 200))
        self._set_combo_value(self.supplier_combo, preset.get("supplier_id"))
        self._set_combo_value(self.location_combo, preset.get("location_id"))
        if preset.get("source"):
            self.lookup_status.setText(f"Prefilled from barcode metadata source: {preset['source']}")

    def auto_fill_from_barcode(self):
        barcode = self.sku_input.text().strip()
        if not barcode:
            return
        metadata = self.data_service.lookup_barcode_metadata(barcode)
        if not metadata:
            self.lookup_status.setText("No metadata found for this barcode yet. You can fill manually.")
            return

        # Only overwrite user-entered fields when empty/default-like.
        if not self.name_input.text().strip():
            self.name_input.setText(str(metadata.get("name", "")))
        if not self.category_input.text().strip():
            self.category_input.setText(str(metadata.get("category", "")))
        if self.unit_input.text().strip().lower() in ("", "pcs"):
            self.unit_input.setText(str(metadata.get("unit", "pcs")))
        if self.cost_input.value() <= 0:
            self.cost_input.setValue(float(metadata.get("unit_cost") or 0.0))
        if self.price_input.value() <= 0:
            self.price_input.setValue(float(metadata.get("unit_price") or 0.0))
        if self.reorder_point.value() in (0, 20):
            self.reorder_point.setValue(int(metadata.get("reorder_point") or 20))
        if self.reorder_qty.value() in (1, 50):
            self.reorder_qty.setValue(int(metadata.get("reorder_qty") or 50))
        if self.max_stock.value() in (1, 200):
            self.max_stock.setValue(int(metadata.get("max_stock") or 200))
        self._set_combo_value(self.supplier_combo, metadata.get("supplier_id"))
        self._set_combo_value(self.location_combo, metadata.get("location_id"))
        self.lookup_status.setText(f"Barcode metadata applied from {metadata.get('source', 'unknown')}.")

    def prepare_for_scan(self):
        """Prepare dialog to receive a physical barcode scanner input."""
        self.sku_input.clear()
        self.sku_input.setFocus()
        self.lookup_status.setText("Ready to scan... please scan now.")

    def handle_scanned_barcode(self, barcode: str):
        """Called by main scanner router when Add Product dialog is active."""
        self.sku_input.setText((barcode or "").strip())
        self.lookup_status.setText(f"Scanned barcode: {barcode}")
        self.auto_fill_from_barcode()
    
    def get_data(self):
        return {
            'sku': self.sku_input.text(),
            'name': self.name_input.text(),
            'category': self.category_input.text(),
            'unit': self.unit_input.text(),
            'unit_cost': self.cost_input.value(),
            'unit_price': self.price_input.value(),
            'reorder_point': self.reorder_point.value(),
            'reorder_qty': self.reorder_qty.value(),
            'max_stock': self.max_stock.value(),
            'location_id': self.location_combo.currentData(),
            'supplier_id': self.supplier_combo.currentData(),
            'expiry_date': self.expiry_input.text() or None,
            'initial_stock': self.initial_stock.value()
        }


class AddLocationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Warehouse Location")
        self.setFixedSize(350, 250)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.zone_input = QLineEdit()
        self.zone_input.setPlaceholderText("e.g., A, B, COLD")
        form.addRow("Zone:", self.zone_input)
        
        self.aisle_input = QLineEdit()
        self.aisle_input.setPlaceholderText("e.g., 01, 02")
        form.addRow("Aisle:", self.aisle_input)
        
        self.rack_input = QLineEdit()
        self.rack_input.setPlaceholderText("e.g., R1, R2")
        form.addRow("Rack:", self.rack_input)
        
        self.bin_input = QLineEdit()
        self.bin_input.setPlaceholderText("e.g., B01, B02")
        form.addRow("Bin:", self.bin_input)
        
        self.capacity = QSpinBox()
        self.capacity.setRange(1, 10000)
        self.capacity.setValue(100)
        form.addRow("Capacity:", self.capacity)
        
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_data(self):
        return {
            'zone': self.zone_input.text(),
            'aisle': self.aisle_input.text(),
            'rack': self.rack_input.text(),
            'bin': self.bin_input.text(),
            'capacity': self.capacity.value()
        }


class StockMoveDialog(QDialog):
    def __init__(self, products, locations, move_type, parent=None):
        super().__init__(parent)
        self.move_type = move_type
        self.setWindowTitle(f"Stock {move_type}")
        self.setFixedSize(400, 300)
        self.setup_ui(products, locations)
    
    def setup_ui(self, products, locations):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.product_combo = QComboBox()
        for p in products:
            self.product_combo.addItem(f"[{p['sku']}] {p['name']}", p['id'])
        form.addRow("Product:", self.product_combo)
        
        self.location_combo = QComboBox()
        for loc in locations:
            label = f"{loc['zone']}-{loc['aisle']}-{loc['rack']}-{loc['bin']}"
            self.location_combo.addItem(label, loc['id'])
        if self.move_type == "TRANSFER":
            form.addRow("From Location:", self.location_combo)
            self.to_location_combo = QComboBox()
            for loc in locations:
                label = f"{loc['zone']}-{loc['aisle']}-{loc['rack']}-{loc['bin']}"
                self.to_location_combo.addItem(label, loc['id'])
            if self.to_location_combo.count() > 1:
                self.to_location_combo.setCurrentIndex(1)
            form.addRow("To Location:", self.to_location_combo)
        else:
            self.to_location_combo = None
            form.addRow("Location:", self.location_combo)
        
        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 10000)
        self.qty_input.setValue(1)
        form.addRow("Quantity:", self.qty_input)
        
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("PO#123, INV#456, etc.")
        form.addRow("Reference:", self.reference)
        
        self.notes = QLineEdit()
        form.addRow("Notes:", self.notes)
        
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_data(self):
        return {
            'product_id': self.product_combo.currentData(),
            'location_id': self.location_combo.currentData(),
            'to_location_id': self.to_location_combo.currentData() if self.to_location_combo else None,
            'quantity': self.qty_input.value(),
            'reference': self.reference.text(),
            'notes': self.notes.text()
        }


class AddSupplierDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Supplier")
        self.setFixedSize(420, 320)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Supplier name")
        form.addRow("Name:", self.name_input)

        self.contact_input = QLineEdit()
        self.contact_input.setPlaceholderText("Contact person (optional)")
        form.addRow("Contact:", self.contact_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Phone (optional)")
        form.addRow("Phone:", self.phone_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email (optional)")
        form.addRow("Email:", self.email_input)

        self.lead_time = QSpinBox()
        self.lead_time.setRange(0, 365)
        self.lead_time.setValue(7)
        form.addRow("Lead Time (days):", self.lead_time)

        self.reliability = QDoubleSpinBox()
        self.reliability.setRange(0.0, 1.0)
        self.reliability.setDecimals(2)
        self.reliability.setSingleStep(0.05)
        self.reliability.setValue(0.8)
        form.addRow("Reliability (0-1):", self.reliability)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            'name': self.name_input.text().strip(),
            'contact_person': self.contact_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'email': self.email_input.text().strip(),
            'lead_time_days': self.lead_time.value(),
            'reliability_score': self.reliability.value()
        }


class CreateUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.setFixedSize(380, 230)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("username")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("password")
        self.role = QComboBox()
        self.role.addItem("admin", "admin")
        self.role.addItem("viewer", "viewer")
        form.addRow("Username:", self.username)
        form.addRow("Password:", self.password)
        form.addRow("Role:", self.role)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return {
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "role": self.role.currentData(),
        }


class PurchaseOrderLinesDialog(QDialog):
    def __init__(self, po: dict, lines: list, parent=None):
        super().__init__(parent)
        self.po = po
        self.lines = lines
        self.setWindowTitle(f"PO خطوط / Lines: PO-{po['id']}")
        self.setFixedSize(700, 420)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        header = QLabel(f"PO-{self.po['id']} | Supplier: {self.po.get('supplier_name','')} | Status: {self.po.get('status','')}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["SKU", "Product", "Qty", "Unit Cost", "Line Total", "Received"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(self.lines))

        for row, ln in enumerate(self.lines):
            table.setItem(row, 0, QTableWidgetItem(ln.get('sku', '')))
            table.setItem(row, 1, QTableWidgetItem(ln.get('name', '')))
            table.setItem(row, 2, QTableWidgetItem(str(ln.get('quantity', 0))))
            table.setItem(row, 3, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{float(ln.get('unit_cost') or 0):.2f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{float(ln.get('line_total') or 0):.2f}"))
            table.setItem(row, 5, QTableWidgetItem(str(ln.get('received_qty', 0))))

        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class ManagementPage(QWidget):
    data_changed = Signal()
    
    def __init__(self, data_service: DataService, can_edit: bool = True, current_username: str = "system"):
        super().__init__()
        self.data_service = data_service
        self.can_edit = can_edit
        self.current_username = current_username
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        header = QLabel("📦 Warehouse Management")
        header.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
            }
        """)
        main_layout.addWidget(header)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #bdc3c7; border-radius: 5px; }
            QTabBar::tab { background: #ecf0f1; color: #2c3e50; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #3498db; color: white; font-weight: bold; }
        """)
        
        self.products_tab = QWidget()
        self.setup_products_tab()
        self.tabs.addTab(self.products_tab, "Products")
        
        self.locations_tab = QWidget()
        self.setup_locations_tab()
        self.tabs.addTab(self.locations_tab, "Locations")
        
        self.stock_tab = QWidget()
        self.setup_stock_tab()
        self.tabs.addTab(self.stock_tab, "Stock Levels")
        
        self.movements_tab = QWidget()
        self.setup_movements_tab()
        self.tabs.addTab(self.movements_tab, "Movements")

        self.suppliers_tab = QWidget()
        self.setup_suppliers_tab()
        self.tabs.addTab(self.suppliers_tab, "Suppliers")

        self.po_tab = QWidget()
        self.setup_po_tab()
        self.tabs.addTab(self.po_tab, "Purchase Orders")

        self.cycle_tab = QWidget()
        self.setup_cycle_tab()
        self.tabs.addTab(self.cycle_tab, "Cycle Count")

        if self.can_edit:
            self.users_tab = QWidget()
            self.setup_users_tab()
            self.tabs.addTab(self.users_tab, "Users")
        
        main_layout.addWidget(self.tabs)
    
    def setup_products_tab(self):
        layout = QVBoxLayout(self.products_tab)
        
        toolbar = QHBoxLayout()
        if self.can_edit:
            add_btn = QPushButton("➕ Add Product")
            add_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            add_btn.clicked.connect(self.add_product)
            toolbar.addWidget(add_btn)
            
            import_btn = QPushButton("📥 Import Excel")
            import_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            import_btn.clicked.connect(self.import_excel)
            toolbar.addWidget(import_btn)
            
            export_btn = QPushButton("📤 Export Excel")
            export_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            export_btn.clicked.connect(self.export_excel)
            toolbar.addWidget(export_btn)
        
        toolbar.addStretch()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_data)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)
        
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(9)
        self.products_table.setHorizontalHeaderLabels(["SKU", "Name", "Category", "Unit", "Unit Cost", "Reorder Pt", "Max Stock", "Supplier", "Actions"])
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.products_table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        layout.addWidget(self.products_table)
    
    def setup_locations_tab(self):
        layout = QVBoxLayout(self.locations_tab)
        
        toolbar = QHBoxLayout()
        if self.can_edit:
            add_btn = QPushButton("➕ Add Location")
            add_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            add_btn.clicked.connect(self.add_location)
            toolbar.addWidget(add_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.locations_table = QTableWidget()
        self.locations_table.setColumnCount(6)
        self.locations_table.setHorizontalHeaderLabels(["Zone", "Aisle", "Rack", "Bin", "Capacity", "Actions"])
        self.locations_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.locations_table)
    
    def setup_stock_tab(self):
        layout = QVBoxLayout(self.stock_tab)
        
        toolbar = QHBoxLayout()
        if self.can_edit:
            receive_btn = QPushButton("📥 Receive Stock")
            receive_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            receive_btn.clicked.connect(lambda: self.do_movement('IN'))
            toolbar.addWidget(receive_btn)
            
            dispatch_btn = QPushButton("📤 Dispatch Stock")
            dispatch_btn.setStyleSheet("QPushButton { background-color: #e67e22; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            dispatch_btn.clicked.connect(lambda: self.do_movement('OUT'))
            toolbar.addWidget(dispatch_btn)
            
            adjust_btn = QPushButton("⚖️ Adjust Stock")
            adjust_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            adjust_btn.clicked.connect(lambda: self.do_movement('ADJUST'))
            toolbar.addWidget(adjust_btn)

            transfer_btn = QPushButton("🔀 Transfer Stock")
            transfer_btn.setStyleSheet("QPushButton { background-color: #16a085; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            transfer_btn.clicked.connect(lambda: self.do_movement('TRANSFER'))
            toolbar.addWidget(transfer_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(9)
        self.stock_table.setHorizontalHeaderLabels(["SKU", "Product", "Zone", "Aisle", "Rack", "Bin", "Qty", "Reserved", "Available"])
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.stock_table)
    
    def setup_movements_tab(self):
        layout = QVBoxLayout(self.movements_tab)
        
        self.movements_table = QTableWidget()
        self.movements_table.setColumnCount(8)
        self.movements_table.setHorizontalHeaderLabels(["Time", "Type", "SKU", "Product", "Qty", "Location", "Reference", "Notes"])
        self.movements_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.movements_table)

    def setup_suppliers_tab(self):
        layout = QVBoxLayout(self.suppliers_tab)

        toolbar = QHBoxLayout()
        if self.can_edit:
            add_btn = QPushButton("➕ Add Supplier")
            add_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
            add_btn.clicked.connect(self.add_supplier)
            toolbar.addWidget(add_btn)
        toolbar.addStretch()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_suppliers)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        self.suppliers_table = QTableWidget()
        self.suppliers_table.setColumnCount(7)
        self.suppliers_table.setHorizontalHeaderLabels(["Name", "Contact", "Phone", "Email", "Lead Time", "Reliability", "Actions"])
        self.suppliers_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.suppliers_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.suppliers_table)

    def setup_po_tab(self):
        layout = QVBoxLayout(self.po_tab)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_purchase_orders)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.po_table = QTableWidget()
        self.po_table.setColumnCount(7)
        self.po_table.setHorizontalHeaderLabels(["PO#", "Supplier", "Status", "Created", "Expected", "Total", "Actions"])
        self.po_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.po_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.po_table)

    def setup_cycle_tab(self):
        layout = QVBoxLayout(self.cycle_tab)
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Load Snapshot")
        refresh_btn.clicked.connect(self.load_cycle_count)
        toolbar.addWidget(refresh_btn)

        if self.can_edit:
            apply_btn = QPushButton("✅ Apply Selected Row")
            apply_btn.setStyleSheet("QPushButton { background-color: #16a085; color: white; border: none; padding: 8px 12px; border-radius: 4px; font-weight: bold; }")
            apply_btn.clicked.connect(self.apply_selected_cycle_count)
            toolbar.addWidget(apply_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.cycle_table = QTableWidget()
        self.cycle_table.setColumnCount(8)
        self.cycle_table.setHorizontalHeaderLabels([
            "SKU", "Product", "Location", "System Qty", "Counted Qty", "Variance", "Product ID", "Location ID"
        ])
        self.cycle_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cycle_table.setColumnHidden(6, True)
        self.cycle_table.setColumnHidden(7, True)
        layout.addWidget(self.cycle_table)

    def setup_users_tab(self):
        layout = QVBoxLayout(self.users_tab)
        toolbar = QHBoxLayout()
        add_btn = QPushButton("➕ Create User")
        add_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }")
        add_btn.clicked.connect(self.create_user)
        toolbar.addWidget(add_btn)
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_users)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.users_table = QTableWidget()
        self.users_table.setColumnCount(7)
        self.users_table.setHorizontalHeaderLabels(["Username", "Role", "Active", "Created", "Last Login", "Reset PW", "Status"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.users_table)
    
    def load_data(self):
        self.load_products()
        self.load_locations()
        self.load_stock()
        self.load_movements()
        self.load_suppliers()
        self.load_purchase_orders()
        self.load_cycle_count()
        if self.can_edit and hasattr(self, "users_table"):
            self.load_users()
    
    def load_products(self):
        products = self.data_service.get_all_products()
        suppliers = self.data_service.get_all_suppliers()
        sup_map = {s['id']: s['name'] for s in suppliers}
        
        self.products_table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.products_table.setItem(row, 0, QTableWidgetItem(p['sku']))
            self.products_table.setItem(row, 1, QTableWidgetItem(p['name']))
            self.products_table.setItem(row, 2, QTableWidgetItem(p.get('category', '')))
            self.products_table.setItem(row, 3, QTableWidgetItem(p['unit']))
            self.products_table.setItem(row, 4, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{p.get('unit_cost', 0):.2f}"))
            self.products_table.setItem(row, 5, QTableWidgetItem(str(p.get('reorder_point', 0))))
            self.products_table.setItem(row, 6, QTableWidgetItem(str(p.get('max_stock', 0))))
            self.products_table.setItem(row, 7, QTableWidgetItem(sup_map.get(p.get('supplier_id'), 'None')))
            
            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; border: none; padding: 4px 8px; border-radius: 3px; }")
            del_btn.clicked.connect(lambda checked, pid=p['id']: self.delete_product(pid))
            if self.can_edit:
                self.products_table.setCellWidget(row, 8, del_btn)
            else:
                self.products_table.setCellWidget(row, 8, QLabel("🔒"))
    
    def load_locations(self):
        locs = self.data_service.get_all_locations()
        self.locations_table.setRowCount(len(locs))
        for row, loc in enumerate(locs):
            self.locations_table.setItem(row, 0, QTableWidgetItem(loc['zone']))
            self.locations_table.setItem(row, 1, QTableWidgetItem(loc['aisle']))
            self.locations_table.setItem(row, 2, QTableWidgetItem(loc['rack']))
            self.locations_table.setItem(row, 3, QTableWidgetItem(loc['bin']))
            self.locations_table.setItem(row, 4, QTableWidgetItem(str(loc['capacity'])))
            
            del_btn = QPushButton("Delete")
            del_btn.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; border: none; padding: 4px 8px; border-radius: 3px; }")
            del_btn.clicked.connect(lambda checked, lid=loc['id']: self.delete_location(lid))
            if self.can_edit:
                self.locations_table.setCellWidget(row, 5, del_btn)
            else:
                self.locations_table.setCellWidget(row, 5, QLabel("🔒"))
    
    def load_stock(self):
        stock = self.data_service.get_all_stock()
        self.stock_table.setRowCount(len(stock))
        for row, s in enumerate(stock):
            self.stock_table.setItem(row, 0, QTableWidgetItem(s['sku']))
            self.stock_table.setItem(row, 1, QTableWidgetItem(s['name']))
            self.stock_table.setItem(row, 2, QTableWidgetItem(s['zone']))
            self.stock_table.setItem(row, 3, QTableWidgetItem(s['aisle']))
            self.stock_table.setItem(row, 4, QTableWidgetItem(s['rack']))
            self.stock_table.setItem(row, 5, QTableWidgetItem(s['bin']))
            self.stock_table.setItem(row, 6, QTableWidgetItem(str(s['quantity'])))
            self.stock_table.setItem(row, 7, QTableWidgetItem(str(s['reserved'])))
            avail = s['quantity'] - s['reserved']
            self.stock_table.setItem(row, 8, QTableWidgetItem(str(avail)))
    
    def load_movements(self):
        moves = self.data_service.get_movements(limit=100)
        self.movements_table.setRowCount(len(moves))
        for row, m in enumerate(moves):
            ts = m['timestamp'][:16] if m['timestamp'] else ''
            self.movements_table.setItem(row, 0, QTableWidgetItem(ts))
            self.movements_table.setItem(row, 1, QTableWidgetItem(m['movement_type']))
            self.movements_table.setItem(row, 2, QTableWidgetItem(m['sku']))
            self.movements_table.setItem(row, 3, QTableWidgetItem(m['name']))
            self.movements_table.setItem(row, 4, QTableWidgetItem(str(m['quantity'])))
            from_loc = f"{m.get('zone','')}-{m.get('aisle','')}-{m.get('rack','')}-{m.get('bin','')}" if m.get('zone') else 'N/A'
            if m.get('movement_type') == 'TRANSFER':
                to_loc = f"{m.get('to_zone','')}-{m.get('to_aisle','')}-{m.get('to_rack','')}-{m.get('to_bin','')}" if m.get('to_zone') else 'N/A'
                loc = f"{from_loc} → {to_loc}"
            else:
                loc = from_loc
            self.movements_table.setItem(row, 5, QTableWidgetItem(loc))
            self.movements_table.setItem(row, 6, QTableWidgetItem(m.get('reference', '')))
            self.movements_table.setItem(row, 7, QTableWidgetItem(m.get('notes', '')))

    def load_suppliers(self):
        sups = self.data_service.get_all_suppliers()
        self.suppliers_table.setRowCount(len(sups))
        for row, s in enumerate(sups):
            self.suppliers_table.setItem(row, 0, QTableWidgetItem(s.get('name', '')))
            self.suppliers_table.setItem(row, 1, QTableWidgetItem(s.get('contact_person', '') or ''))
            self.suppliers_table.setItem(row, 2, QTableWidgetItem(s.get('phone', '') or ''))
            self.suppliers_table.setItem(row, 3, QTableWidgetItem(s.get('email', '') or ''))
            self.suppliers_table.setItem(row, 4, QTableWidgetItem(str(s.get('lead_time_days', 0))))
            self.suppliers_table.setItem(row, 5, QTableWidgetItem(f"{float(s.get('reliability_score') or 0):.2f}"))

            deactivate_btn = QPushButton("Deactivate")
            deactivate_btn.setStyleSheet("QPushButton { background-color: #e67e22; color: white; border: none; padding: 4px 8px; border-radius: 3px; }")
            deactivate_btn.clicked.connect(lambda checked, sid=s['id']: self.deactivate_supplier(sid))
            if self.can_edit:
                self.suppliers_table.setCellWidget(row, 6, deactivate_btn)
            else:
                self.suppliers_table.setCellWidget(row, 6, QLabel("🔒"))

    def load_purchase_orders(self):
        pos = self.data_service.get_purchase_orders()
        self.po_table.setRowCount(len(pos))
        for row, po in enumerate(pos):
            self.po_table.setItem(row, 0, QTableWidgetItem(f"PO-{po['id']}"))
            self.po_table.setItem(row, 1, QTableWidgetItem(po.get('supplier_name', '')))
            self.po_table.setItem(row, 2, QTableWidgetItem(po.get('status', '')))
            self.po_table.setItem(row, 3, QTableWidgetItem((po.get('created_at') or '')[:16]))
            self.po_table.setItem(row, 4, QTableWidgetItem((po.get('expected_date') or '')[:10]))
            self.po_table.setItem(row, 5, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{float(po.get('total_cost') or 0):.2f}"))

            actions = QWidget()
            a_layout = QHBoxLayout(actions)
            a_layout.setContentsMargins(0, 0, 0, 0)
            a_layout.setSpacing(6)

            view_btn = QPushButton("View")
            view_btn.clicked.connect(lambda checked, po_row=po: self.view_po(po_row))
            a_layout.addWidget(view_btn)

            recv_btn = QPushButton("Receive")
            recv_btn.setStyleSheet("QPushButton { background-color: #27ae60; color: white; border: none; padding: 4px 8px; border-radius: 3px; }")
            recv_btn.clicked.connect(lambda checked, po_id=po['id']: self.receive_po(po_id))
            if self.can_edit:
                a_layout.addWidget(recv_btn)

            self.po_table.setCellWidget(row, 6, actions)

    def load_cycle_count(self):
        stock = self.data_service.get_all_stock()
        self.cycle_table.setRowCount(len(stock))
        for row, s in enumerate(stock):
            loc = f"{s.get('zone','')}-{s.get('aisle','')}-{s.get('rack','')}-{s.get('bin','')}"
            system_qty = int(s.get("quantity") or 0)
            self.cycle_table.setItem(row, 0, QTableWidgetItem(s.get("sku", "")))
            self.cycle_table.setItem(row, 1, QTableWidgetItem(s.get("name", "")))
            self.cycle_table.setItem(row, 2, QTableWidgetItem(loc))
            self.cycle_table.setItem(row, 3, QTableWidgetItem(str(system_qty)))
            self.cycle_table.setItem(row, 4, QTableWidgetItem(str(system_qty)))
            self.cycle_table.setItem(row, 5, QTableWidgetItem("0"))
            self.cycle_table.setItem(row, 6, QTableWidgetItem(str(s.get("product_id", ""))))
            self.cycle_table.setItem(row, 7, QTableWidgetItem(str(s.get("location_id", ""))))

    def apply_selected_cycle_count(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot apply cycle count adjustments.")
            return
        row = self.cycle_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Cycle Count", "Select a row first.")
            return
        try:
            system_qty = int(self.cycle_table.item(row, 3).text())
            counted_qty = int(self.cycle_table.item(row, 4).text())
            variance = counted_qty - system_qty
            self.cycle_table.item(row, 5).setText(str(variance))

            product_id = int(self.cycle_table.item(row, 6).text())
            location_id = int(self.cycle_table.item(row, 7).text())
            sku = self.cycle_table.item(row, 0).text()

            ok, msg = self.data_service.apply_cycle_count(
                product_id=product_id,
                location_id=location_id,
                counted_qty=counted_qty,
                reference="CYCLE-COUNT",
                notes=f"Cycle count for {sku}",
                user=self.current_username
            )
            if ok:
                QMessageBox.information(self, "Cycle Count Applied", msg)
                self.load_stock()
                self.load_movements()
                self.load_cycle_count()
                self.data_changed.emit()
            else:
                QMessageBox.warning(self, "Cycle Count Failed", msg)
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", f"Counted quantity must be a valid integer.\n{e}")

    def load_users(self):
        users = self.data_service.get_all_users()
        self.users_table.setRowCount(len(users))
        for row, u in enumerate(users):
            self.users_table.setItem(row, 0, QTableWidgetItem(u.get("username", "")))
            self.users_table.setItem(row, 1, QTableWidgetItem(u.get("role", "")))
            self.users_table.setItem(row, 2, QTableWidgetItem("Yes" if u.get("is_active") else "No"))
            self.users_table.setItem(row, 3, QTableWidgetItem((u.get("created_at") or "")[:16]))
            self.users_table.setItem(row, 4, QTableWidgetItem((u.get("last_login") or "")[:16]))

            reset_btn = QPushButton("Reset")
            reset_btn.clicked.connect(lambda checked, uid=u["id"], un=u["username"]: self.reset_password(uid, un))
            self.users_table.setCellWidget(row, 5, reset_btn)

            toggle_btn = QPushButton("Disable" if u.get("is_active") else "Enable")
            toggle_btn.clicked.connect(
                lambda checked, uid=u["id"], active=bool(u.get("is_active")): self.toggle_user_active(uid, active)
            )
            self.users_table.setCellWidget(row, 6, toggle_btn)

    def create_user(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot manage users.")
            return
        dlg = CreateUserDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if not data["username"] or not data["password"]:
                QMessageBox.warning(self, "Invalid", "Username and password are required.")
                return
            try:
                self.data_service.create_user(data["username"], data["password"], role=data["role"], is_active=True)
                self.load_users()
                QMessageBox.information(self, "Success", f"User '{data['username']}' created.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create user: {e}")

    def reset_password(self, user_id: int, username: str):
        from PySide6.QtWidgets import QInputDialog
        new_pw, ok = QInputDialog.getText(self, "Reset Password", f"New password for '{username}':", QLineEdit.Password)
        if not ok:
            return
        if not new_pw:
            QMessageBox.warning(self, "Invalid", "Password cannot be empty.")
            return
        if self.data_service.reset_user_password(user_id, new_pw):
            QMessageBox.information(self, "Password Reset", f"Password updated for '{username}'.")
        else:
            QMessageBox.warning(self, "Failed", "Password reset failed.")

    def toggle_user_active(self, user_id: int, currently_active: bool):
        if self.data_service.set_user_active(user_id, not currently_active):
            self.load_users()
        else:
            QMessageBox.warning(self, "Failed", "Could not update user status.")
    
    def add_product(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot add products.")
            return
        dialog = AddProductDialog(self.data_service, self.data_service.get_all_locations(), self.data_service.get_all_suppliers(), self)
        if dialog.exec():
            data = dialog.get_data()
            if data['sku'] and data['name']:
                initial_stock = int(data.pop('initial_stock', 0) or 0)
                pid = self.data_service.add_product(**data)
                if initial_stock > 0:
                    # Put initial stock into the selected/default location if available
                    location_id = data.get('location_id') or (self.data_service.get_all_locations()[0]['id'] if self.data_service.get_all_locations() else None)
                    if location_id:
                        self.data_service.set_stock(pid, location_id, initial_stock)
                        self.data_service.record_movement(
                            product_id=pid,
                            movement_type='IN',
                            quantity=initial_stock,
                            location_id=location_id,
                            reference='INITIAL',
                            notes='Initial stock set on product creation',
                            user=self.current_username
                        )
                self.load_products()
                self.load_stock()
                self.load_movements()
                self.data_changed.emit()
                QMessageBox.information(self, "Success", f"Product {data['sku']} added!")
    
    def add_location(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot add locations.")
            return
        dialog = AddLocationDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if all([data['zone'], data['aisle'], data['rack'], data['bin']]):
                self.data_service.add_location(**data)
                self.load_locations()
                self.data_changed.emit()
                QMessageBox.information(self, "Success", "Location added!")

    def add_supplier(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot add suppliers.")
            return
        dialog = AddSupplierDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['name']:
                QMessageBox.warning(self, "Invalid", "Supplier name is required.")
                return
            self.data_service.add_supplier(**data)
            self.load_suppliers()
            self.data_changed.emit()
            QMessageBox.information(self, "Success", "Supplier added!")

    def deactivate_supplier(self, supplier_id: int):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot update suppliers.")
            return
        reply = QMessageBox.question(self, "Confirm", "Deactivate this supplier?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.data_service.deactivate_supplier(supplier_id)
            self.load_suppliers()
            self.data_changed.emit()

    def view_po(self, po: dict):
        lines = self.data_service.get_purchase_order_lines(po['id'])
        dialog = PurchaseOrderLinesDialog(po, lines, self)
        dialog.exec()

    def receive_po(self, po_id: int):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot receive purchase orders.")
            return
        reply = QMessageBox.question(self, "Receive PO", f"Mark PO-{po_id} as received and add stock?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        ok = self.data_service.receive_purchase_order(po_id, received_by=self.current_username)
        if ok:
            QMessageBox.information(self, "Received", f"PO-{po_id} received and stock updated.")
            self.load_stock()
            self.load_movements()
            self.load_purchase_orders()
            self.data_changed.emit()
        else:
            QMessageBox.critical(self, "Error", "Failed to receive this PO.")
    
    def do_movement(self, move_type):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot post stock movements.")
            return
        products = self.data_service.get_all_products()
        locations = self.data_service.get_all_locations()
        if not products:
            QMessageBox.warning(self, "No Products", "Add products first.")
            return
        if not locations:
            QMessageBox.warning(self, "No Locations", "Add locations first.")
            return
        
        dialog = StockMoveDialog(products, locations, move_type, self)
        if dialog.exec():
            data = dialog.get_data()
            if move_type == 'TRANSFER':
                if data.get('location_id') == data.get('to_location_id'):
                    QMessageBox.warning(self, "Invalid Transfer", "From and To locations must be different.")
                    return
                ok, msg = self.data_service.transfer_stock(
                    product_id=data['product_id'],
                    from_location_id=data['location_id'],
                    to_location_id=data['to_location_id'],
                    quantity=data['quantity'],
                    reference=data['reference'],
                    notes=data['notes'],
                    user=self.current_username
                )
                if not ok:
                    QMessageBox.warning(self, "Transfer Failed", msg)
                    return
                self.load_stock()
                self.load_movements()
                self.data_changed.emit()
                QMessageBox.information(self, "Success", msg)
                return

            # Record movement
            self.data_service.record_movement(
                product_id=data['product_id'],
                movement_type=move_type,
                quantity=data['quantity'],
                location_id=data['location_id'],
                reference=data['reference'],
                notes=data['notes'],
                user=self.current_username
            )
            
            # Update stock levels
            stock_rows = self.data_service.get_stock(data['product_id'], data['location_id'])
            current_qty = stock_rows[0]['quantity'] if stock_rows else 0
            
            if move_type == 'IN':
                new_qty = current_qty + data['quantity']
            elif move_type == 'OUT':
                new_qty = max(0, current_qty - data['quantity'])
            elif move_type == 'ADJUST':
                new_qty = data['quantity']
            else:
                new_qty = current_qty
            
            self.data_service.set_stock(data['product_id'], data['location_id'], new_qty)
            
            self.load_stock()
            self.load_movements()
            self.data_changed.emit()
            QMessageBox.information(self, "Success", f"Stock {move_type} recorded!")
    
    def delete_product(self, product_id):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot delete products.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this product?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.data_service.delete_product(product_id)
            self.load_products()
            self.data_changed.emit()
    
    def delete_location(self, location_id):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot delete locations.")
            return
        reply = QMessageBox.question(self, "Confirm", "Delete this location?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            deleted = self.data_service.delete_location(location_id)
            if not deleted:
                QMessageBox.warning(
                    self, "Cannot Delete",
                    "This location is still in use (has stock levels) or could not be deleted."
                )
                return
            self.load_locations()
            self.data_changed.emit()
    
    def import_excel(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot import data.")
            return
        try:
            from utils.excel_utils import import_warehouse_stock_workbook
        except ImportError:
            QMessageBox.critical(self, "Error", "openpyxl not installed. Run: pip install openpyxl")
            return
        
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Products from Excel", "", "Excel Files (*.xlsx)")
        if not filepath:
            return
        
        try:
            result = import_warehouse_stock_workbook(filepath)
            QMessageBox.information(
                self, "Import Complete",
                f"Imported: {result.get('imported')}\nUpdated: {result.get('updated')}\nErrors: {len(result.get('errors', []))}"
            )
            self.load_data()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))
    
    def export_excel(self):
        if not self.can_edit:
            QMessageBox.warning(self, "Read Only", "Viewer role cannot export data.")
            return
        try:
            from utils.excel_utils import export_warehouse_stock_workbook
        except ImportError:
            QMessageBox.critical(self, "Error", "openpyxl not installed. Run: pip install openpyxl")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Warehouse Workbook", "warehouse_stock_export.xlsx", "Excel Files (*.xlsx)")
        if not filepath:
            return
        
        try:
            export_warehouse_stock_workbook(filepath)
            QMessageBox.information(self, "Export Complete", f"Exported warehouse workbook to {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
