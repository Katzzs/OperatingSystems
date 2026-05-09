"""
Barcode Scanner Integration - HID Keyboard Wedge Support

Physical barcode scanners act as USB keyboards. This module detects
rapid keyboard input (barcode scan) vs human typing, captures the
barcode string, and triggers warehouse actions.
"""

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QKeyEvent
from typing import Optional, Callable
from services.data_service import DataService


class BarcodeScanner(QObject):
    """
    Detects barcode scans from HID keyboard-wedge scanners.
    
    Scanners type characters extremely fast (<50ms between keys).
    Humans type much slower (>100ms between keys).
    We use this timing difference to distinguish scan from typing.
    """
    
    barcode_scanned = Signal(str)  # Emits the decoded barcode string
    
    # Timing threshold: if keys arrive faster than this, it's a scan
    SCAN_THRESHOLD_MS = 80
    # Minimum length to be considered a barcode
    MIN_BARCODE_LENGTH = 4
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._buffer = []
        self._last_key_time = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush_buffer)
        
        # Track if we're in "scan mode" (rapid input detected)
        self._scan_mode = False
        self._enabled = True
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            self._buffer.clear()
            self._scan_mode = False
    
    def process_key_event(self, event: QKeyEvent) -> bool:
        """
        Process a key event. Returns True if the event was consumed (barcode scan).
        Returns False if it should be passed through to normal input handling.
        """
        if not self._enabled:
            return False
        
        # Only handle key presses
        if event.type() != QKeyEvent.Type.KeyPress:
            return False
        
        key = event.key()
        
        # Enter/Return terminates a barcode scan
        if key in (16777220, 16777221):  # Qt.Key_Return, Qt.Key_Enter
            if self._scan_mode and len(self._buffer) >= self.MIN_BARCODE_LENGTH:
                barcode = ''.join(self._buffer)
                self._buffer.clear()
                self._scan_mode = False
                self.barcode_scanned.emit(barcode)
                return True
            else:
                self._buffer.clear()
                self._scan_mode = False
                return False
        
        # Escape cancels scan mode
        if key == 16777216:  # Qt.Key_Escape
            self._buffer.clear()
            self._scan_mode = False
            return False
        
        # Ignore modifier keys
        if key in (16777248, 16777249, 16777251, 16777252):  # Shift, Ctrl, Alt, Caps
            return False
        
        # Get character from key event
        text = event.text()
        if not text or len(text) != 1:
            return False
        
        # Check timing - if this key arrived very fast after the last one,
        # we're likely in scan mode
        import time
        current_time = int(time.time() * 1000)
        
        if self._last_key_time > 0:
            elapsed = current_time - self._last_key_time
            if elapsed < self.SCAN_THRESHOLD_MS:
                # Rapid input - barcode scan mode
                if not self._scan_mode:
                    self._scan_mode = True
            else:
                # Slow input - human typing, reset unless already deep in scan
                if not self._scan_mode or len(self._buffer) < 2:
                    self._buffer.clear()
                    self._scan_mode = False
        
        self._last_key_time = current_time
        self._buffer.append(text)
        
        # Start/reset flush timer
        self._timer.stop()
        self._timer.start(200)
        
        # If we're in scan mode, consume the key event
        if self._scan_mode:
            return True
        
        return False
    
    def _flush_buffer(self):
        """Flush buffer if no keys received for a while"""
        if self._scan_mode and len(self._buffer) >= self.MIN_BARCODE_LENGTH:
            barcode = ''.join(self._buffer)
            self.barcode_scanned.emit(barcode)
        self._buffer.clear()
        self._scan_mode = False
        self._last_key_time = 0


class BarcodeLookup:
    """Lookup helper for barcode-to-product resolution"""
    
    def __init__(self, data_service: DataService):
        self.data_service = data_service
    
    def find_product_by_barcode(self, barcode: str) -> Optional[dict]:
        """
        Find a product by barcode/SKU.
        
        Tries exact SKU match first, then partial SKU, then name.
        """
        products = self.data_service.get_all_products()
        barcode_upper = barcode.strip().upper()
        
        # Exact SKU match
        for p in products:
            if p['sku'].upper() == barcode_upper:
                return p
        
        # Partial SKU match (barcode might contain SKU as substring)
        for p in products:
            if barcode_upper in p['sku'].upper() or p['sku'].upper() in barcode_upper:
                return p
        
        # Name match (sometimes barcodes encode product names)
        for p in products:
            if barcode_upper in p['name'].upper():
                return p
        
        return None
    
    def get_stock_for_product(self, product_id: int) -> list:
        """Get all stock levels for a product across locations"""
        return self.data_service.get_stock(product_id)
    
    def record_barcode_scan(self, barcode: str, product_id: int = None, 
                           action: str = "lookup", quantity: int = 0,
                           location_id: int = None):
        """Record that a barcode was scanned for audit trail"""
        # Safe audit trail even when product_id is unknown
        self.data_service.record_barcode_scan(
            barcode=barcode,
            product_id=product_id,
            action=action,
            quantity=quantity,
            location_id=location_id,
            notes=f"Barcode scan: {action}"
        )
