"""Arranca a aplicacao Field Shift e abre-a no browser.

Uso (a partir da pasta do projeto):
    python run.py

Porque existe: em Windows o comando "streamlit" muitas vezes nao esta no PATH,
e na primeira vez o Streamlit para a pedir um email. Este arranque chama o
Streamlit atraves do proprio Python e em modo silencioso, por isso nenhum dos
dois acontece.
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
    sys.exit("Faltam as dependencias. Corra primeiro:\n"
             f"    {Path(sys.executable).name} -m pip install -r requirements.txt")

url = f"http://localhost:{PORT}"
print(f"A abrir o Field Shift em {url} (Ctrl+C para parar)")
threading.Timer(4, webbrowser.open, args=[url]).start()
try:
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                    "--server.headless", "true", "--server.port", str(PORT),
                    "--browser.gatherUsageStats", "false"], cwd=ROOT)
except KeyboardInterrupt:
    pass
