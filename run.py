"""Starts the Field Shift app and opens it in the browser.

Usage (from the project folder):
    python run.py

Why it exists: on Windows the "streamlit" command is often not on the PATH,
and on first run Streamlit stops to ask for an email. This launcher calls
Streamlit through Python itself, in headless mode, so neither happens.
"""
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

PORT = 8501
ROOT = Path(__file__).resolve().parent

try:
    import streamlit  # noqa: F401
except ImportError:
    sys.exit("Dependencies are missing. First run:\n"
             f"    {Path(sys.executable).name} -m pip install -r requirements.txt")

url = f"http://localhost:{PORT}"
print(f"Opening Field Shift at {url} (Ctrl+C to stop)")
threading.Timer(4, webbrowser.open, args=[url]).start()
try:
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                    "--server.headless", "true", "--server.port", str(PORT),
                    "--browser.gatherUsageStats", "false"], cwd=ROOT)
except KeyboardInterrupt:
    pass
