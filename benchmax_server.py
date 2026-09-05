import sys, os, traceback, logging
from datetime import datetime

# Set env so backend.logging_setup uses JSON file logging for .exe builds
os.environ.setdefault("BENCHMAX_LOG_LEVEL", "DEBUG")

from backend.logging_setup import configure_logging
configure_logging()
logging.info("Starting BenchMax...")
logging.info(f"sys.executable: {sys.executable}")
logging.info(f"sys.argv: {sys.argv}")
logging.info(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")

try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    webbrowser_ok = False
    try:
        import webbrowser
        webbrowser.open("http://localhost:8000")
        webbrowser_ok = True
    except Exception as e:
        logging.warning(f"Could not open browser: {e}")

    import uvicorn
    from backend.main import app
    logging.info("App imported successfully, starting uvicorn...")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
except Exception:
    traceback.print_exc()
    logging.exception("Fatal startup error")
    print("\nPress Enter to exit...")
    input()
