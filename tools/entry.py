"""PyInstaller entry point: python tools/entry.py <app>. Imports the app as a package so relative imports work."""
import importlib
import sys

app = sys.argv.pop(1)
importlib.import_module(f"apps.{app}.main").main()
