"""
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
    # Persist user data outside PyInstaller temp extraction folder
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
URGENCY_WEIGHT = 0.35
FREQUENCY_WEIGHT = 0.25
IMPACT_WEIGHT = 0.30
RECENCY_WEIGHT = 0.10

# Priority thresholds
HIGH_PRIORITY_THRESHOLD = 75
MEDIUM_PRIORITY_THRESHOLD = 50

# Popup settings
POPUP_COOLDOWN_SECONDS = 30
MIN_CONFIDENCE_THRESHOLD = 0.6
ENABLE_POPUPS = True
