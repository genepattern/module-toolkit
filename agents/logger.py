"""
Logging and display utilities for the module generation process.
"""
from datetime import datetime


class Logger:
    """Logging and display utilities for the module generation process."""

    @staticmethod
    def print_status(message: str, level: str = "INFO"):
        """Print status message with timestamp and level."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    @staticmethod
    def print_section(title: str):
        """Print a section header."""
        print("\n" + "=" * 60)
        print(f" {title}")
        print("=" * 60)

