import sys, os, traceback, logging
from datetime import datetime

# Log crashes to a file
_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")
logging.basicConfig(
    filename=_log_path, level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
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
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
except Exception:
    traceback.print_exc()
    logging.exception("Fatal startup error")
    print("\nPress Enter to exit...")
    input()
