"""
Reports UI - Warehouse KPIs, ABC Analysis, Insights
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QGridLayout, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from typing import Dict, List
import utils
import config
from services.data_service import DataService
from logic.decision_engine import DecisionEngine


class StatCard(QFrame):
    def __init__(self, title: str, value: str, color: str = "#3498db"):
        super().__init__()
        self.setup_ui(title, value, color)
    
    def setup_ui(self, title: str, value: str, color: str):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedSize(220, 100)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("QLabel { font-size: 12px; color: #7f8c8d; font-weight: bold; }")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"QLabel {{ font-size: 24px; font-weight: bold; color: {color}; }}")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)
        layout.addStretch()


class InsightCard(QFrame):
    def __init__(self, insight: Dict):
        super().__init__()
        self.insight = insight
        self.setup_ui()
    
    def setup_ui(self):
        self.setFrameStyle(QFrame.StyledPanel)
        self.setFixedHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)
        
        header_layout = QHBoxLayout()
        
        type_icons = {'risk': '⚠️', 'trend': '📈', 'summary': '📊'}
        icon = type_icons.get(self.insight['type'], 'ℹ️')
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(self.insight['title'])
        title_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #2c3e50; }")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        desc_label = QLabel(self.insight['description'])
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("QLabel { font-size: 13px; color: #7f8c8d; }")
        layout.addWidget(desc_label)
        
        severity = self.insight['severity']
        severity_color = utils.get_severity_color(severity)
        
        severity_bar = QProgressBar()
        severity_bar.setFixedHeight(6)
        severity_bar.setTextVisible(False)
        severity_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #ecf0f1; border-radius: 3px; }}
            QProgressBar::chunk {{ background-color: {severity_color}; border-radius: 3px; }}
        """)
        severity_values = {'critical': 100, 'high': 100, 'medium': 60, 'low': 30}
        severity_bar.setValue(severity_values.get(severity, 50))
        layout.addWidget(severity_bar)


class ReportsPage(QWidget):
    def __init__(self, data_service: DataService, decision_engine: DecisionEngine):
        super().__init__()
        self.data_service = data_service
        self.decision_engine = decision_engine
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        header = QLabel("📊 Warehouse Reports & Insights")
        header.setStyleSheet("QLabel { font-size: 28px; font-weight: bold; color: #2c3e50; }")
        main_layout.addWidget(header)
        
        # Stats row
        stats_layout = QHBoxLayout()
        
        self.total_products_card = StatCard("Total SKUs", "0", "#3498db")
        self.inventory_value_card = StatCard("Inventory Value", f"{config.CURRENCY_SYMBOL}0", "#27ae60")
        self.total_locations_card = StatCard("Locations", "0", "#9b59b6")
        self.low_stock_card = StatCard("Below Reorder", "0", "#e74c3c")
        
        stats_layout.addWidget(self.total_products_card)
        stats_layout.addWidget(self.total_locations_card)
        stats_layout.addWidget(self.inventory_value_card)
        stats_layout.addWidget(self.low_stock_card)
        stats_layout.addStretch()
        
        main_layout.addLayout(stats_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        
        # Insights tab
        self.insights_tab = QWidget()
        insights_layout = QVBoxLayout(self.insights_tab)
        self.insights_scroll = QScrollArea()
        self.insights_scroll.setWidgetResizable(True)
        self.insights_container = QWidget()
        self.insights_layout = QVBoxLayout(self.insights_container)
        self.insights_layout.setSpacing(15)
        self.insights_scroll.setWidget(self.insights_container)
        insights_layout.addWidget(self.insights_scroll)
        self.tabs.addTab(self.insights_tab, "Insights")
        
        # ABC Analysis tab
        self.abc_tab = QWidget()
        abc_layout = QVBoxLayout(self.abc_tab)
        self.abc_table = QTableWidget()
        self.abc_table.setColumnCount(4)
        self.abc_table.setHorizontalHeaderLabels(["Class", "SKU", "Product", "Stock Value"])
        self.abc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        abc_layout.addWidget(self.abc_table)
        self.tabs.addTab(self.abc_tab, "ABC Analysis")
        
        # Category Breakdown tab
        self.category_tab = QWidget()
        cat_layout = QVBoxLayout(self.category_tab)
        self.cat_table = QTableWidget()
        self.cat_table.setColumnCount(4)
        self.cat_table.setHorizontalHeaderLabels(["Category", "Product Count", "Total Qty", "Total Value"])
        self.cat_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cat_layout.addWidget(self.cat_table)
        self.tabs.addTab(self.category_tab, "Category Breakdown")
        
        # Location Utilization tab
        self.location_tab = QWidget()
        loc_layout = QVBoxLayout(self.location_tab)
        self.loc_table = QTableWidget()
        self.loc_table.setColumnCount(6)
        self.loc_table.setHorizontalHeaderLabels(["Zone", "Aisle", "Rack", "Bin", "Capacity", "Utilization"])
        self.loc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        loc_layout.addWidget(self.loc_table)
        self.tabs.addTab(self.location_tab, "Location Utilization")
        
        main_layout.addWidget(self.tabs)
        
        refresh_btn = QPushButton("🔄 Refresh Reports")
        refresh_btn.setStyleSheet("QPushButton { background-color: #95a5a6; color: white; border: none; padding: 10px; border-radius: 5px; font-weight: bold; font-size: 13px; }")
        refresh_btn.clicked.connect(self.load_data)
        main_layout.addWidget(refresh_btn)
    
    def load_data(self):
        self.load_insights()
        self.load_abc()
        self.load_categories()
        self.load_locations()
        self.update_stats()
    
    def load_insights(self):
        # Clear existing
        while self.insights_layout.count():
            item = self.insights_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        insights = self.decision_engine.generate_insights()
        for insight in insights:
            card = InsightCard(insight)
            self.insights_layout.addWidget(card)
        
        if not insights:
            no_insights = QLabel("No insights available")
            no_insights.setStyleSheet("QLabel { color: #95a5a6; font-style: italic; }")
            no_insights.setAlignment(Qt.AlignCenter)
            self.insights_layout.addWidget(no_insights)
        
        self.insights_layout.addStretch()
    
    def load_abc(self):
        abc = self.decision_engine.analyze_abc()
        
        all_rows = []
        for cls in ['A', 'B', 'C']:
            for item in abc.get(cls, []):
                all_rows.append([cls, item['sku'], item['name'], f"{config.CURRENCY_SYMBOL}{item['stock_value']:.2f}"])
        
        self.abc_table.setRowCount(len(all_rows))
        for row, data in enumerate(all_rows):
            for col, val in enumerate(data):
                self.abc_table.setItem(row, col, QTableWidgetItem(val))
    
    def load_categories(self):
        cats = self.data_service.get_category_breakdown()
        self.cat_table.setRowCount(len(cats))
        for row, cat in enumerate(cats):
            self.cat_table.setItem(row, 0, QTableWidgetItem(cat.get('category', 'Uncategorized')))
            self.cat_table.setItem(row, 1, QTableWidgetItem(str(cat['product_count'])))
            self.cat_table.setItem(row, 2, QTableWidgetItem(str(cat['total_qty'])))
            self.cat_table.setItem(row, 3, QTableWidgetItem(f"{config.CURRENCY_SYMBOL}{cat['total_value']:.2f}"))
    
    def load_locations(self):
        locs = self.data_service.get_location_utilization()
        self.loc_table.setRowCount(len(locs))
        for row, loc in enumerate(locs):
            self.loc_table.setItem(row, 0, QTableWidgetItem(loc['zone']))
            self.loc_table.setItem(row, 1, QTableWidgetItem(loc['aisle']))
            self.loc_table.setItem(row, 2, QTableWidgetItem(loc['rack']))
            self.loc_table.setItem(row, 3, QTableWidgetItem(loc['bin']))
            self.loc_table.setItem(row, 4, QTableWidgetItem(str(loc['capacity'])))
            
            load = loc.get('current_load', 0)
            cap = loc['capacity']
            pct = min(100, int(load / cap * 100)) if cap > 0 else 0
            self.loc_table.setItem(row, 5, QTableWidgetItem(f"{load}/{cap} ({pct}%)"))
    
    def update_stats(self):
        products = self.data_service.get_all_products()
        locations = self.data_service.get_all_locations()
        value = self.data_service.get_inventory_value()
        low = self.data_service.get_below_reorder_products()
        
        self._update_card(self.total_products_card, "Total SKUs", str(len(products)), "#3498db")
        self._update_card(self.total_locations_card, "Locations", str(len(locations)), "#9b59b6")
        self._update_card(self.inventory_value_card, "Inventory Value", f"{config.CURRENCY_SYMBOL}{value:.0f}", "#27ae60")
        self._update_card(self.low_stock_card, "Below Reorder", str(len(low)), "#e74c3c")
    
    def _update_card(self, card, title, value, color):
        # Find and update the value label (second child)
        layout = card.layout()
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, QLabel) and widget.text() != title:
                widget.setText(value)
                widget.setStyleSheet(f"QLabel {{ font-size: 24px; font-weight: bold; color: {color}; }}")
