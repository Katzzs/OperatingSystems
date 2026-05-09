# Smart Warehouse DSS (Smart WMS)

Desktop warehouse management and decision support system built with Python, PySide6, and SQLite.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

## Default Login

- `admin` / `admin123`
- `viewer` / `viewer123`

## Core Modules

- `Admin Window` - Dashboard, Inventory, Reports, Settings (full access)
- `Viewer Window` - Dashboard, Inventory (read-only), Reports
- `Inventory` - viewer mode hides add/import/export/edit action controls

## Build

```bash
pyinstaller dss.spec
```

or:

```powershell
.\build.ps1
```

Build output:
- `dist/SmartDSS.exe`

## Utility Scripts

- `python scripts/data/generate_warehouse_excels.py`
- `python scripts/tests/test_warehouse.py`
- `python scripts/tests/test_barcode.py`

## Full Documentation

See `DOCS.md` for:
- system overview and architecture
- login and role behavior
- tab-by-tab feature explanation
- navigation guide
- manual testing checklist
- barcode and purchase order workflows
