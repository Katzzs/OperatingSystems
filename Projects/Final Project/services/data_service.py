"""
Data Service Layer - Warehouse Stock Management
"""

import sqlite3
import json
import urllib.request
import urllib.error
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config


class DataService:
    """Service layer for warehouse database operations"""
    
    def __init__(self):
        self.db_path = config.DB_PATH
        self._initialize_database()
    
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_database(self):
        """Initialize warehouse database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Products / SKUs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                unit TEXT DEFAULT 'pcs',
                unit_cost REAL DEFAULT 0.0,
                unit_price REAL DEFAULT 0.0,
                reorder_point INTEGER DEFAULT 20,
                reorder_qty INTEGER DEFAULT 50,
                max_stock INTEGER DEFAULT 200,
                location_id INTEGER,
                supplier_id INTEGER,
                expiry_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Locations (Zone -> Aisle -> Rack -> Bin)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone TEXT NOT NULL,
                aisle TEXT NOT NULL,
                rack TEXT NOT NULL,
                bin TEXT NOT NULL,
                capacity INTEGER DEFAULT 100,
                current_load INTEGER DEFAULT 0,
                UNIQUE(zone, aisle, rack, bin)
            )
        """)
        
        # Stock Levels (per product per location)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 0,
                reserved INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (location_id) REFERENCES locations(id),
                UNIQUE(product_id, location_id)
            )
        """)
        
        # Stock Movements (IN, OUT, ADJUST, TRANSFER)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                location_id INTEGER,
                to_location_id INTEGER,
                movement_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                reference TEXT,
                notes TEXT,
                user TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        
        # Suppliers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                lead_time_days INTEGER DEFAULT 7,
                reliability_score REAL DEFAULT 0.8,
                active BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Purchase Orders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER,
                status TEXT DEFAULT 'draft',
                expected_date TEXT,
                total_cost REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                received_at TEXT
            )
        """)
        
        # PO Lines
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                po_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost REAL,
                line_total REAL,
                received_qty INTEGER DEFAULT 0
            )
        """)
        
        # Alerts & Recommendations history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                message TEXT NOT NULL,
                target_id INTEGER,
                target_type TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                target_id INTEGER,
                target_type TEXT,
                score REAL,
                priority_level TEXT,
                reason TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                executed BOOLEAN DEFAULT FALSE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_behavior (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                recommendation_id INTEGER,
                accepted BOOLEAN,
                context_data TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Barcode scans (audit trail that can exist without a product match)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcode_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                product_id INTEGER,
                action TEXT DEFAULT 'lookup',
                quantity INTEGER DEFAULT 0,
                location_id INTEGER,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (location_id) REFERENCES locations(id)
            )
        """)

        # Barcode profile cache (learned from created products / external lookup)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS barcode_profiles (
                barcode TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                unit TEXT,
                unit_cost REAL DEFAULT 0.0,
                unit_price REAL DEFAULT 0.0,
                reorder_point INTEGER DEFAULT 20,
                reorder_qty INTEGER DEFAULT 50,
                max_stock INTEGER DEFAULT 200,
                supplier_id INTEGER,
                location_id INTEGER,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User accounts / RBAC
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
        """)

        # Seed defaults so "Add Product" selectors are usable on first run
        cursor.execute("SELECT COUNT(*) as c FROM locations")
        if (cursor.fetchone() or {'c': 0})['c'] == 0:
            cursor.execute("""
                INSERT INTO locations (zone, aisle, rack, bin, capacity, current_load)
                VALUES ('MAIN', '01', 'R1', 'B1', 100000, 0)
            """)

        cursor.execute("SELECT COUNT(*) as c FROM suppliers WHERE active = TRUE")
        if (cursor.fetchone() or {'c': 0})['c'] == 0:
            cursor.execute("""
                INSERT INTO suppliers (name, contact_person, phone, email, lead_time_days, reliability_score, active)
                VALUES ('Default Supplier', '', '', '', 7, 0.8, TRUE)
            """)

        # Seed default users
        cursor.execute("SELECT COUNT(*) as c FROM users")
        if (cursor.fetchone() or {'c': 0})['c'] == 0:
            self._seed_default_users(cursor)
        
        conn.commit()
        conn.close()

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        payload = f"{salt}:{password}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _seed_default_users(self, cursor):
        """
        Creates initial users:
        - admin / admin123 (admin)
        - viewer / viewer123 (viewer)
        """
        defaults = [
            ("admin", "admin123", "admin"),
            ("viewer", "viewer123", "viewer"),
        ]
        now = datetime.now().isoformat()
        for username, password, role in defaults:
            salt = secrets.token_hex(16)
            pwh = self._hash_password(password, salt)
            cursor.execute("""
                INSERT INTO users (username, password_hash, salt, role, is_active, created_at)
                VALUES (?, ?, ?, ?, TRUE, ?)
            """, (username, pwh, salt, role, now))
    
    # ========== PRODUCTS ==========
    
    def add_product(self, sku, name, category='', unit='pcs',
                    unit_cost=0.0, unit_price=0.0,
                    reorder_point=20, reorder_qty=50,
                    max_stock=200, location_id=None,
                    supplier_id=None, expiry_date=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (sku, name, category, unit, unit_cost, unit_price,
                reorder_point, reorder_qty, max_stock, location_id, supplier_id, expiry_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sku, name, category, unit, unit_cost, unit_price,
              reorder_point, reorder_qty, max_stock, location_id, supplier_id, expiry_date))
        conn.commit()
        pid = cursor.lastrowid
        conn.close()
        # Learn barcode/product profile for future auto-fill
        try:
            self.upsert_barcode_profile(
                barcode=sku,
                name=name,
                category=category,
                unit=unit,
                unit_cost=unit_cost,
                unit_price=unit_price,
                reorder_point=reorder_point,
                reorder_qty=reorder_qty,
                max_stock=max_stock,
                supplier_id=supplier_id,
                location_id=location_id,
            )
        except Exception:
            pass
        return pid
    
    def get_all_products(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY name")
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products
    
    def get_product(self, product_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def delete_product(self, product_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    
    # ========== LOCATIONS ==========
    
    def add_location(self, zone, aisle, rack, bin, capacity=100):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO locations (zone, aisle, rack, bin, capacity)
            VALUES (?, ?, ?, ?, ?)
        """, (zone, aisle, rack, bin, capacity))
        conn.commit()
        lid = cursor.lastrowid
        conn.close()
        return lid
    
    def get_all_locations(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations ORDER BY zone, aisle, rack, bin")
        locs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return locs
    
    def get_location(self, location_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    # ========== STOCK LEVELS ==========
    
    def set_stock(self, product_id, location_id, quantity, reserved=0):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO stock_levels (product_id, location_id, quantity, reserved, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(product_id, location_id) DO UPDATE SET
                quantity = excluded.quantity,
                reserved = excluded.reserved,
                updated_at = excluded.updated_at
        """, (product_id, location_id, quantity, reserved, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_stock(self, product_id, location_id=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        if location_id:
            cursor.execute("""
                SELECT sl.*, p.sku, p.name, p.unit, l.zone, l.aisle, l.rack, l.bin
                FROM stock_levels sl
                JOIN products p ON sl.product_id = p.id
                JOIN locations l ON sl.location_id = l.id
                WHERE sl.product_id = ? AND sl.location_id = ?
            """, (product_id, location_id))
        else:
            cursor.execute("""
                SELECT sl.*, p.sku, p.name, p.unit, p.reorder_point, p.reorder_qty, p.max_stock,
                       l.zone, l.aisle, l.rack, l.bin
                FROM stock_levels sl
                JOIN products p ON sl.product_id = p.id
                JOIN locations l ON sl.location_id = l.id
                WHERE sl.product_id = ?
            """, (product_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_all_stock(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sl.*, p.sku, p.name, p.unit, p.reorder_point, p.reorder_qty, p.max_stock,
                   p.unit_cost, p.expiry_date,
                   l.zone, l.aisle, l.rack, l.bin
            FROM stock_levels sl
            JOIN products p ON sl.product_id = p.id
            JOIN locations l ON sl.location_id = l.id
            ORDER BY p.name
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_total_stock_for_product(self, product_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total FROM stock_levels WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()
        conn.close()
        return row['total'] if row else 0
    
    def get_available_stock(self, product_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(quantity - reserved), 0) as available
            FROM stock_levels WHERE product_id = ?
        """, (product_id,))
        row = cursor.fetchone()
        conn.close()
        return row['available'] if row else 0
    
    # ========== STOCK MOVEMENTS ==========
    
    def record_movement(self, product_id, movement_type, quantity,
                        location_id=None, to_location_id=None,
                        reference='', notes='', user='system'):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO stock_movements
            (product_id, location_id, to_location_id, movement_type, quantity, reference, notes, user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (product_id, location_id, to_location_id, movement_type, quantity, reference, notes, user))
        conn.commit()
        mid = cursor.lastrowid
        conn.close()
        return mid

    def transfer_stock(self, product_id: int, from_location_id: int, to_location_id: int, quantity: int,
                       reference: str = "", notes: str = "", user: str = "system") -> tuple[bool, str]:
        """
        Transfer stock between locations atomically.
        Returns (success, message).
        """
        if from_location_id == to_location_id:
            return False, "Source and destination locations must be different."
        if quantity <= 0:
            return False, "Transfer quantity must be greater than zero."

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT quantity, reserved FROM stock_levels
                WHERE product_id = ? AND location_id = ?
            """, (product_id, from_location_id))
            from_row = cursor.fetchone()
            from_qty = (from_row['quantity'] if from_row else 0)
            from_reserved = (from_row['reserved'] if from_row else 0)
            from_available = from_qty - from_reserved

            if from_available < quantity:
                conn.close()
                return False, f"Insufficient available stock at source ({from_available} available)."

            # Destination row
            cursor.execute("""
                SELECT quantity, reserved FROM stock_levels
                WHERE product_id = ? AND location_id = ?
            """, (product_id, to_location_id))
            to_row = cursor.fetchone()
            to_qty = (to_row['quantity'] if to_row else 0)
            to_reserved = (to_row['reserved'] if to_row else 0)

            now = datetime.now().isoformat()

            # Deduct source
            new_from_qty = from_qty - quantity
            cursor.execute("""
                INSERT INTO stock_levels (product_id, location_id, quantity, reserved, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(product_id, location_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    reserved = excluded.reserved,
                    updated_at = excluded.updated_at
            """, (product_id, from_location_id, new_from_qty, from_reserved, now))

            # Add destination
            new_to_qty = to_qty + quantity
            cursor.execute("""
                INSERT INTO stock_levels (product_id, location_id, quantity, reserved, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(product_id, location_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    reserved = excluded.reserved,
                    updated_at = excluded.updated_at
            """, (product_id, to_location_id, new_to_qty, to_reserved, now))

            # Record movement
            cursor.execute("""
                INSERT INTO stock_movements
                (product_id, location_id, to_location_id, movement_type, quantity, reference, notes, user, timestamp)
                VALUES (?, ?, ?, 'TRANSFER', ?, ?, ?, ?, ?)
            """, (product_id, from_location_id, to_location_id, quantity, reference, notes, user, now))

            conn.commit()
            conn.close()
            return True, "Stock transfer completed."
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f"Transfer failed: {e}"
    
    def get_movements(self, product_id=None, limit=100):
        conn = self._get_connection()
        cursor = conn.cursor()
        if product_id:
            cursor.execute("""
                SELECT sm.*, p.sku, p.name,
                       l.zone, l.aisle, l.rack, l.bin,
                       l2.zone as to_zone, l2.aisle as to_aisle, l2.rack as to_rack, l2.bin as to_bin
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                LEFT JOIN locations l ON sm.location_id = l.id
                LEFT JOIN locations l2 ON sm.to_location_id = l2.id
                WHERE sm.product_id = ?
                ORDER BY sm.timestamp DESC
                LIMIT ?
            """, (product_id, limit))
        else:
            cursor.execute("""
                SELECT sm.*, p.sku, p.name,
                       l.zone, l.aisle, l.rack, l.bin,
                       l2.zone as to_zone, l2.aisle as to_aisle, l2.rack as to_rack, l2.bin as to_bin
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                LEFT JOIN locations l ON sm.location_id = l.id
                LEFT JOIN locations l2 ON sm.to_location_id = l2.id
                ORDER BY sm.timestamp DESC
                LIMIT ?
            """, (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_movement_stats(self, product_id, days=30):
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # OUT movements
        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0) as out_qty, COUNT(*) as out_count
            FROM stock_movements
            WHERE product_id = ? AND movement_type = 'OUT' AND timestamp >= ?
        """, (product_id, cutoff))
        out_row = cursor.fetchone()
        
        # IN movements
        cursor.execute("""
            SELECT COALESCE(SUM(quantity), 0) as in_qty, COUNT(*) as in_count
            FROM stock_movements
            WHERE product_id = ? AND movement_type = 'IN' AND timestamp >= ?
        """, (product_id, cutoff))
        in_row = cursor.fetchone()
        
        conn.close()
        return {
            'in_qty': in_row['in_qty'] or 0,
            'in_count': in_row['in_count'] or 0,
            'out_qty': out_row['out_qty'] or 0,
            'out_count': out_row['out_count'] or 0,
            'net_change': (in_row['in_qty'] or 0) - (out_row['out_qty'] or 0)
        }
    
    # ========== SUPPLIERS ==========
    
    def add_supplier(self, name, contact_person='', phone='',
                     email='', lead_time_days=7, reliability_score=0.8):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO suppliers (name, contact_person, phone, email, lead_time_days, reliability_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, contact_person, phone, email, lead_time_days, reliability_score))
        conn.commit()
        sid = cursor.lastrowid
        conn.close()
        return sid
    
    def get_all_suppliers(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM suppliers WHERE active = TRUE ORDER BY name")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_supplier(self, supplier_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def deactivate_supplier(self, supplier_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE suppliers SET active = FALSE WHERE id = ?", (supplier_id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    
    # ========== PURCHASE ORDERS ==========
    
    def create_purchase_order(self, supplier_id, expected_date=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO purchase_orders (supplier_id, expected_date, status)
            VALUES (?, ?, 'draft')
        """, (supplier_id, expected_date))
        conn.commit()
        poid = cursor.lastrowid
        conn.close()
        return poid
    
    def add_po_line(self, po_id, product_id, quantity, unit_cost):
        conn = self._get_connection()
        cursor = conn.cursor()
        line_total = quantity * unit_cost
        cursor.execute("""
            INSERT INTO purchase_order_lines (po_id, product_id, quantity, unit_cost, line_total)
            VALUES (?, ?, ?, ?, ?)
        """, (po_id, product_id, quantity, unit_cost, line_total))
        conn.commit()
        conn.close()

        # Update PO total_cost (best-effort)
        try:
            self._recalculate_po_total(po_id)
        except Exception:
            pass

    def _recalculate_po_total(self, po_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(line_total), 0) as total
            FROM purchase_order_lines
            WHERE po_id = ?
        """, (po_id,))
        row = cursor.fetchone()
        total = row['total'] if row else 0.0
        cursor.execute("UPDATE purchase_orders SET total_cost = ? WHERE id = ?", (total, po_id))
        conn.commit()
        conn.close()
    
    def get_purchase_orders(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT po.*, s.name as supplier_name
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            ORDER BY po.created_at DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_purchase_order_lines(self, po_id: int):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pol.*, p.sku, p.name
            FROM purchase_order_lines pol
            JOIN products p ON pol.product_id = p.id
            WHERE pol.po_id = ?
            ORDER BY pol.id ASC
        """, (po_id,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def set_purchase_order_status(self, po_id: int, status: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", (status, po_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

    def receive_purchase_order(self, po_id: int, received_by: str = "system") -> bool:
        """
        Mark a purchase order as received and apply stock increases.
        For simplicity, receives full ordered qty into the product's default location,
        falling back to the first available location.
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,))
        po = cursor.fetchone()
        if not po:
            conn.close()
            return False

        if po['status'] == 'received':
            conn.close()
            return True

        cursor.execute("""
            SELECT pol.*, p.location_id as default_location
            FROM purchase_order_lines pol
            JOIN products p ON pol.product_id = p.id
            WHERE pol.po_id = ?
        """, (po_id,))
        lines = [dict(r) for r in cursor.fetchall()]

        # Determine fallback location
        cursor.execute("SELECT id FROM locations ORDER BY id ASC LIMIT 1")
        fallback_loc = cursor.fetchone()
        fallback_loc_id = fallback_loc['id'] if fallback_loc else None

        for line in lines:
            product_id = line['product_id']
            qty = int(line.get('quantity') or 0)
            if qty <= 0:
                continue

            location_id = line.get('default_location') or fallback_loc_id
            if not location_id:
                continue

            # Current stock row
            cursor.execute("""
                SELECT quantity, reserved FROM stock_levels
                WHERE product_id = ? AND location_id = ?
            """, (product_id, location_id))
            sl = cursor.fetchone()
            current_qty = sl['quantity'] if sl else 0
            reserved = sl['reserved'] if sl else 0
            new_qty = current_qty + qty

            cursor.execute("""
                INSERT INTO stock_levels (product_id, location_id, quantity, reserved, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(product_id, location_id) DO UPDATE SET
                    quantity = excluded.quantity,
                    reserved = excluded.reserved,
                    updated_at = excluded.updated_at
            """, (product_id, location_id, new_qty, reserved, datetime.now().isoformat()))

            cursor.execute("""
                INSERT INTO stock_movements
                (product_id, location_id, movement_type, quantity, reference, notes, user, timestamp)
                VALUES (?, ?, 'IN', ?, ?, ?, ?, ?)
            """, (
                product_id, location_id, qty, f"PO-{po_id}",
                "Received via purchase order", received_by, datetime.now().isoformat()
            ))

            cursor.execute("""
                UPDATE purchase_order_lines
                SET received_qty = ?
                WHERE id = ?
            """, (qty, line['id']))

        cursor.execute("""
            UPDATE purchase_orders
            SET status = 'received', received_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), po_id))

        conn.commit()
        conn.close()
        return True
    
    # ========== ALERTS ==========
    
    def create_alert(self, alert_type, severity, message,
                     target_id=None, target_type=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alerts (alert_type, severity, message, target_id, target_type)
            VALUES (?, ?, ?, ?, ?)
        """, (alert_type, severity, message, target_id, target_type))
        conn.commit()
        aid = cursor.lastrowid
        conn.close()
        return aid
    
    def get_active_alerts(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM alerts
            WHERE is_active = TRUE
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def resolve_alert(self, alert_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE alerts
            SET is_active = FALSE, resolved_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), alert_id))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    
    # ========== ANALYTICS ==========
    
    def get_below_reorder_products(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, COALESCE(SUM(sl.quantity), 0) as total_stock
            FROM products p
            LEFT JOIN stock_levels sl ON p.id = sl.product_id
            GROUP BY p.id
            HAVING total_stock <= p.reorder_point
            ORDER BY total_stock ASC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_expiring_products(self, days=30):
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT p.*, COALESCE(SUM(sl.quantity), 0) as total_stock
            FROM products p
            LEFT JOIN stock_levels sl ON p.id = sl.product_id
            WHERE p.expiry_date IS NOT NULL AND p.expiry_date <= ?
            GROUP BY p.id
            HAVING total_stock > 0
            ORDER BY p.expiry_date ASC
        """, (cutoff,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_dead_stock(self, days=90):
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("""
            SELECT p.*, COALESCE((SELECT SUM(quantity) FROM stock_levels WHERE product_id = p.id), 0) as total_stock
            FROM products p
            WHERE p.id NOT IN (
                SELECT DISTINCT product_id FROM stock_movements
                WHERE movement_type = 'OUT' AND timestamp >= ?
            )
            AND COALESCE((SELECT SUM(quantity) FROM stock_levels WHERE product_id = p.id), 0) > 0
            ORDER BY total_stock DESC
        """, (cutoff,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_inventory_value(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COALESCE(SUM(sl.quantity * p.unit_cost), 0) as total_value
            FROM stock_levels sl
            JOIN products p ON sl.product_id = p.id
        """)
        row = cursor.fetchone()
        conn.close()
        return row['total_value'] or 0.0
    
    def get_category_breakdown(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.category,
                   COUNT(DISTINCT p.id) as product_count,
                   COALESCE(SUM(sl.quantity), 0) as total_qty,
                   COALESCE(SUM(sl.quantity * p.unit_cost), 0) as total_value
            FROM products p
            LEFT JOIN stock_levels sl ON p.id = sl.product_id
            GROUP BY p.category
            ORDER BY total_value DESC
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    
    def get_location_utilization(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT l.*, COALESCE(SUM(sl.quantity), 0) as current_load
            FROM locations l
            LEFT JOIN stock_levels sl ON l.id = sl.location_id
            GROUP BY l.id
            ORDER BY l.zone, l.aisle, l.rack, l.bin
        """)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    # ========== RECOMMENDATIONS & LEARNING ==========

    def save_recommendation(self, action_type: str, target_id: Optional[int], target_type: str,
                            score: float, priority_level: str, reason: str,
                            confidence: float = 0.5, executed: bool = False) -> int:
        """Persist a recommendation for audit/history."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recommendations
            (action_type, target_id, target_type, score, priority_level, reason, confidence, executed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            action_type, target_id, target_type, score, priority_level, reason,
            confidence, 1 if executed else 0, datetime.now().isoformat()
        ))
        conn.commit()
        rid = cursor.lastrowid
        conn.close()
        return rid

    def log_behavior(self, action_type: str, recommendation_id: Optional[int],
                     accepted: bool, context_data: str = "") -> int:
        """Log a user accept/ignore behavior event."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_behavior (action_type, recommendation_id, accepted, context_data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (action_type, recommendation_id, 1 if accepted else 0, context_data or "", datetime.now().isoformat()))
        conn.commit()
        bid = cursor.lastrowid
        conn.close()
        return bid

    def get_acceptance_rate(self, action_type: str, days: int = 30) -> float:
        """Acceptance rate for an action type over the past N days."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute("""
            SELECT
                CAST(SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) AS FLOAT) /
                CAST(COUNT(*) AS FLOAT) as rate
            FROM user_behavior
            WHERE action_type = ? AND timestamp >= ?
        """, (action_type, cutoff))
        row = cursor.fetchone()
        conn.close()
        if not row or row['rate'] is None:
            return 0.5  # Neutral default when there is no data
        try:
            return float(row['rate'])
        except Exception:
            return 0.5

    # ========== BARCODE SCANS ==========

    def record_barcode_scan(self, barcode: str, product_id: Optional[int] = None,
                            action: str = "lookup", quantity: int = 0,
                            location_id: Optional[int] = None, notes: str = "") -> int:
        """Record barcode scan audit event (safe even if product is unknown)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO barcode_scans
            (barcode, product_id, action, quantity, location_id, timestamp, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (barcode, product_id, action, quantity, location_id, datetime.now().isoformat(), notes or ""))
        conn.commit()
        sid = cursor.lastrowid
        conn.close()
        return sid

    def get_barcode_profile(self, barcode: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM barcode_profiles WHERE barcode = ?", (barcode,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def upsert_barcode_profile(self, barcode: str, name: str = "", category: str = "", unit: str = "pcs",
                               unit_cost: float = 0.0, unit_price: float = 0.0,
                               reorder_point: int = 20, reorder_qty: int = 50, max_stock: int = 200,
                               supplier_id: Optional[int] = None, location_id: Optional[int] = None):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO barcode_profiles
            (barcode, name, category, unit, unit_cost, unit_price, reorder_point, reorder_qty, max_stock, supplier_id, location_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(barcode) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                unit = excluded.unit,
                unit_cost = excluded.unit_cost,
                unit_price = excluded.unit_price,
                reorder_point = excluded.reorder_point,
                reorder_qty = excluded.reorder_qty,
                max_stock = excluded.max_stock,
                supplier_id = excluded.supplier_id,
                location_id = excluded.location_id,
                updated_at = excluded.updated_at
        """, (
            barcode, name or "", category or "", unit or "pcs",
            float(unit_cost or 0), float(unit_price or 0),
            int(reorder_point or 20), int(reorder_qty or 50), int(max_stock or 200),
            supplier_id, location_id, datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def lookup_barcode_metadata(self, barcode: str) -> Optional[Dict]:
        """
        Resolve barcode metadata for Add Product auto-fill.
        Priority:
        1) Local barcode_profiles cache
        2) OpenFoodFacts lookup (best-effort, optional network)
        """
        barcode = (barcode or "").strip()
        if not barcode:
            return None

        cached = self.get_barcode_profile(barcode)
        if cached and cached.get("name"):
            return {
                "sku": barcode,
                "name": cached.get("name", ""),
                "category": cached.get("category", ""),
                "unit": cached.get("unit", "pcs") or "pcs",
                "unit_cost": float(cached.get("unit_cost") or 0),
                "unit_price": float(cached.get("unit_price") or 0),
                "reorder_point": int(cached.get("reorder_point") or 20),
                "reorder_qty": int(cached.get("reorder_qty") or 50),
                "max_stock": int(cached.get("max_stock") or 200),
                "supplier_id": cached.get("supplier_id"),
                "location_id": cached.get("location_id"),
                "source": "local_cache",
            }

        # Best-effort external lookup; safe fallback on failure.
        try:
            url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
            req = urllib.request.Request(url, headers={"User-Agent": "SmartDSS/1.0"})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if payload.get("status") != 1:
                return None
            product = payload.get("product", {}) or {}
            name = (product.get("product_name") or product.get("product_name_en") or "").strip()
            category = ""
            cats = product.get("categories_tags") or []
            if cats:
                category = str(cats[0]).replace("en:", "").replace("-", " ").title()

            if not name:
                return None

            metadata = {
                "sku": barcode,
                "name": name,
                "category": category or "Uncategorized",
                "unit": "pcs",
                "unit_cost": 0.0,
                "unit_price": 0.0,
                "reorder_point": 20,
                "reorder_qty": 50,
                "max_stock": 200,
                "source": "openfoodfacts",
            }
            # Save lightweight cache for next scans
            try:
                self.upsert_barcode_profile(
                    barcode=barcode,
                    name=metadata["name"],
                    category=metadata["category"],
                    unit=metadata["unit"],
                    reorder_point=metadata["reorder_point"],
                    reorder_qty=metadata["reorder_qty"],
                    max_stock=metadata["max_stock"],
                )
            except Exception:
                pass
            return metadata
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError):
            return None

    # ========== DELETE HELPERS ==========

    def delete_location(self, location_id: int) -> bool:
        """
        Delete a location if it is not referenced by stock levels.
        Returns True if deleted, False otherwise.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as c FROM stock_levels WHERE location_id = ?", (location_id,))
        in_use = (cursor.fetchone() or {'c': 0})['c'] > 0
        if in_use:
            conn.close()
            return False

        cursor.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    # ========== AUTH / USERS ==========

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password_hash, salt, role, is_active
            FROM users
            WHERE username = ?
        """, ((username or "").strip(),))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        user = dict(row)
        if not bool(user.get("is_active")):
            conn.close()
            return None

        expected = user.get("password_hash", "")
        computed = self._hash_password(password or "", user.get("salt", ""))
        if computed != expected:
            conn.close()
            return None

        cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user["id"]))
        conn.commit()
        conn.close()
        return {
            "id": user["id"],
            "username": user["username"],
            "role": user.get("role", "viewer"),
        }

    def create_user(self, username: str, password: str, role: str = "viewer", is_active: bool = True) -> int:
        role = role if role in ("admin", "viewer") else "viewer"
        salt = secrets.token_hex(16)
        pwh = self._hash_password(password, salt)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, password_hash, salt, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ((username or "").strip(), pwh, salt, role, 1 if is_active else 0, datetime.now().isoformat()))
        conn.commit()
        uid = cursor.lastrowid
        conn.close()
        return uid

    def get_all_users(self) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, role, is_active, created_at, last_login
            FROM users
            ORDER BY username ASC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def set_user_active(self, user_id: int, is_active: bool) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def set_user_role(self, user_id: int, role: str) -> bool:
        role = role if role in ("admin", "viewer") else "viewer"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    def reset_user_password(self, user_id: int, new_password: str) -> bool:
        salt = secrets.token_hex(16)
        pwh = self._hash_password(new_password or "", salt)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (pwh, salt, user_id))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed

    # ========== CYCLE COUNT ==========

    def apply_cycle_count(self, product_id: int, location_id: int, counted_qty: int,
                          reference: str = "CYCLE-COUNT", notes: str = "", user: str = "system") -> tuple[bool, str]:
        """
        Adjust system stock to match counted quantity and record ADJUST movement (difference only).
        """
        if counted_qty < 0:
            return False, "Counted quantity cannot be negative."

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT quantity, reserved
            FROM stock_levels
            WHERE product_id = ? AND location_id = ?
        """, (product_id, location_id))
        row = cursor.fetchone()
        current_qty = row["quantity"] if row else 0
        reserved = row["reserved"] if row else 0
        diff = counted_qty - current_qty

        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO stock_levels (product_id, location_id, quantity, reserved, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(product_id, location_id) DO UPDATE SET
                quantity = excluded.quantity,
                reserved = excluded.reserved,
                updated_at = excluded.updated_at
        """, (product_id, location_id, counted_qty, reserved, now))

        if diff != 0:
            cursor.execute("""
                INSERT INTO stock_movements
                (product_id, location_id, movement_type, quantity, reference, notes, user, timestamp)
                VALUES (?, ?, 'ADJUST', ?, ?, ?, ?, ?)
            """, (
                product_id, location_id, abs(diff), reference,
                notes or f"Cycle count adjustment ({'+' if diff > 0 else '-'}{abs(diff)})",
                user, now
            ))

        conn.commit()
        conn.close()
        if diff == 0:
            return True, "No variance detected."
        return True, f"Variance applied: {'+' if diff > 0 else '-'}{abs(diff)}"
