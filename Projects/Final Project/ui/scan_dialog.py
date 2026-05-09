"""
Barcode Scan Dialog - Quick action dialog that appears after a scan
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QComboBox, QLineEdit, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from services.data_service import DataService
from logic.barcode_scanner import BarcodeLookup


class ScanActionDialog(QDialog):
    """
    Dialog that appears after scanning a barcode.
    Shows product info and allows quick stock operations.
    """
    
    stock_updated = Signal()
    
    def __init__(self, barcode: str, product: dict, data_service: DataService, parent=None):
        super().__init__(parent)
        self.barcode = barcode
        self.product = product
        self.data_service = data_service
        self.lookup = BarcodeLookup(data_service)
        
        self.setWindowTitle(f"Barcode Scan: {barcode}")
        self.setFixedSize(500, 420)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(18)
        
        # Barcode display
        barcode_label = QLabel(f"📷 Scanned: {self.barcode}")
        barcode_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #2c3e50; }")
        layout.addWidget(barcode_label)
        
        # Product info card
        info_frame = QFrame()
        info_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border-radius: 8px; padding: 15px; }")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)
        
        sku_label = QLabel(f"SKU: {self.product['sku']}")
        sku_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #3498db; }")
        info_layout.addWidget(sku_label)
        
        name_label = QLabel(f"Name: {self.product['name']}")
        name_label.setStyleSheet("QLabel { font-size: 13px; color: #2c3e50; }")
        info_layout.addWidget(name_label)
        
        category_label = QLabel(f"Category: {self.product.get('category', 'N/A')}")
        category_label.setStyleSheet("QLabel { font-size: 12px; color: #7f8c8d; }")
        info_layout.addWidget(category_label)
        
        # Current stock across locations
        stock_rows = self.lookup.get_stock_for_product(self.product['id'])
        total_stock = sum(row['quantity'] for row in stock_rows)
        total_avail = sum(row['quantity'] - row['reserved'] for row in stock_rows)
        
        stock_label = QLabel(f"Current Stock: {total_stock} {self.product['unit']} (Available: {total_avail})")
        stock_label.setStyleSheet("QLabel { font-size: 13px; font-weight: bold; color: #27ae60; }")
        info_layout.addWidget(stock_label)
        
        if stock_rows:
            for row in stock_rows:
                loc_text = f"  📍 {row['zone']}-{row['aisle']}-{row['rack']}-{row['bin']}: {row['quantity']} {self.product['unit']}"
                loc_label = QLabel(loc_text)
                loc_label.setStyleSheet("QLabel { font-size: 11px; color: #95a5a6; }")
                info_layout.addWidget(loc_label)
        
        layout.addWidget(info_frame)
        
        # Action selection
        action_label = QLabel("Quick Action:")
        action_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #2c3e50; }")
        layout.addWidget(action_label)
        
        # Location selector
        loc_layout = QHBoxLayout()
        loc_layout.addWidget(QLabel("Location:"))
        self.location_combo = QComboBox()
        locations = self.data_service.get_all_locations()
        for loc in locations:
            label = f"{loc['zone']}-{loc['aisle']}-{loc['rack']}-{loc['bin']}"
            self.location_combo.addItem(label, loc['id'])
        # Pre-select default location if product has one
        if self.product.get('location_id'):
            idx = self.location_combo.findData(self.product['location_id'])
            if idx >= 0:
                self.location_combo.setCurrentIndex(idx)
        loc_layout.addWidget(self.location_combo)
        layout.addLayout(loc_layout)
        
        # Quantity
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Quantity:"))
        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 10000)
        self.qty_input.setValue(1)
        self.qty_input.setFixedWidth(100)
        qty_layout.addWidget(self.qty_input)
        qty_layout.addStretch()
        layout.addLayout(qty_layout)
        
        # Reference
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Reference:"))
        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("e.g., PO-123, INV-456, Return-001")
        ref_layout.addWidget(self.ref_input)
        layout.addLayout(ref_layout)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        self.receive_btn = QPushButton("📥 Receive (IN)")
        self.receive_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #219150; }
            QPushButton:pressed { background-color: #1e8449; }
        """)
        self.receive_btn.clicked.connect(lambda: self.execute_action('IN'))
        buttons_layout.addWidget(self.receive_btn)
        
        self.dispatch_btn = QPushButton("📤 Dispatch (OUT)")
        self.dispatch_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #d35400; }
            QPushButton:pressed { background-color: #a04000; }
        """)
        self.dispatch_btn.clicked.connect(lambda: self.execute_action('OUT'))
        buttons_layout.addWidget(self.dispatch_btn)
        
        self.adjust_btn = QPushButton("⚖️ Adjust")
        self.adjust_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #8e44ad; }
            QPushButton:pressed { background-color: #6c3483; }
        """)
        self.adjust_btn.clicked.connect(lambda: self.execute_action('ADJUST'))
        buttons_layout.addWidget(self.adjust_btn)
        
        layout.addLayout(buttons_layout)
        
        # Lookup only button
        lookup_btn = QPushButton("🔍 Lookup Only (Close)")
        lookup_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        lookup_btn.clicked.connect(self.reject)
        layout.addWidget(lookup_btn)
        
        layout.addStretch()
    
    def execute_action(self, movement_type: str):
        qty = self.qty_input.value()
        location_id = self.location_combo.currentData()
        reference = self.ref_input.text() or f"SCAN-{self.barcode}"
        
        # Record movement
        self.data_service.record_movement(
            product_id=self.product['id'],
            movement_type=movement_type,
            quantity=qty,
            location_id=location_id,
            reference=reference,
            notes=f"Barcode scan action: {movement_type}"
        )
        
        # Update stock level
        stock_rows = self.data_service.get_stock(self.product['id'], location_id)
        current_qty = stock_rows[0]['quantity'] if stock_rows else 0
        
        if movement_type == 'IN':
            new_qty = current_qty + qty
        elif movement_type == 'OUT':
            new_qty = max(0, current_qty - qty)
        elif movement_type == 'ADJUST':
            new_qty = qty
        else:
            new_qty = current_qty
        
        self.data_service.set_stock(self.product['id'], location_id, new_qty)
        
        # Record scan audit
        self.lookup.record_barcode_scan(
            barcode=self.barcode,
            product_id=self.product['id'],
            action=movement_type,
            quantity=qty,
            location_id=location_id
        )
        
        QMessageBox.information(
            self, "Success",
            f"{movement_type}: {qty} {self.product['unit']} of {self.product['name']}\n"
            f"Location: {self.location_combo.currentText()}\n"
            f"Reference: {reference}"
        )
        
        self.stock_updated.emit()
        self.accept()


class UnknownBarcodeDialog(QDialog):
    """Dialog shown when a scanned barcode doesn't match any product"""
    
    create_product = Signal(str)
    
    def __init__(self, barcode: str, parent=None):
        super().__init__(parent)
        self.barcode = barcode
        self.setWindowTitle(f"Unknown Barcode: {barcode}")
        self.setFixedSize(400, 200)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        warning = QLabel("⚠️ No product found for this barcode")
        warning.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #e74c3c; }")
        layout.addWidget(warning)
        
        barcode_label = QLabel(f"Scanned: {self.barcode}")
        barcode_label.setStyleSheet("QLabel { font-size: 14px; color: #2c3e50; }")
        layout.addWidget(barcode_label)
        
        hint = QLabel("This barcode does not match any SKU in the system.")
        hint.setStyleSheet("QLabel { font-size: 12px; color: #7f8c8d; font-style: italic; }")
        layout.addWidget(hint)
        
        create_btn = QPushButton("➕ Create Product with this SKU")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        create_btn.clicked.connect(self._on_create)
        layout.addWidget(create_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        layout.addStretch()
    
    def _on_create(self):
        self.create_product.emit(self.barcode)
        self.accept()
