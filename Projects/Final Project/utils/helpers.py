"""
Helper utilities for the application
"""

from datetime import datetime, timedelta
from typing import Optional


def format_datetime(dt_str: str, format: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime string for display"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime(format)
    except:
        return dt_str


def format_date(dt_str: str, format: str = "%Y-%m-%d") -> str:
    """Format date string for display"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime(format)
    except:
        return dt_str


def get_relative_time(dt_str: str) -> str:
    """Get relative time string (e.g., '2 hours ago')"""
    try:
        dt = datetime.fromisoformat(dt_str)
        delta = datetime.now() - dt
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except:
        return dt_str


def get_priority_color(priority: str) -> str:
    """Get color code for priority level"""
    colors = {
        'HIGH': '#e74c3c',      # Red
        'MEDIUM': '#f39c12',    # Orange
        'LOW': '#27ae60'        # Green
    }
    return colors.get(priority.upper(), '#95a5a6')


def get_severity_color(severity: str) -> str:
    """Get color code for severity level"""
    colors = {
        'high': '#e74c3c',
        'medium': '#f39c12',
        'low': '#3498db'
    }
    return colors.get(severity.lower(), '#95a5a6')


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if too long"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def calculate_percentage(value: int, total: int) -> float:
    """Calculate percentage safely"""
    if total == 0:
        return 0.0
    return round((value / total) * 100, 1)
