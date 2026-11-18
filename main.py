import argparse
import logging
import os
import sys
from pathlib import Path

from config.config import Config


def _configure_tcl_paths():
    tcl_root = Path(sys.base_prefix) / "tcl"
    tcl_library = os.environ.get("TCL_LIBRARY")
    if not tcl_library or not (Path(tcl_library) / "init.tcl").is_file():
        candidates = sorted(tcl_root.glob("tcl*/init.tcl"))
        if candidates:
            os.environ["TCL_LIBRARY"] = str(candidates[-1].parent)
    tk_library = os.environ.get("TK_LIBRARY")
    if not tk_library or not (Path(tk_library) / "tk.tcl").is_file():
        candidates = sorted(tcl_root.glob("tk*/tk.tcl"))
        if candidates:
            os.environ["TK_LIBRARY"] = str(candidates[-1].parent)


def main():
    parser = argparse.ArgumentParser(description="Egyetemi NFC jelenlétkezelő")
    parser.add_argument("--web", action="store_true", help="REST API indítása")
    parser.add_argument("--host", default=getattr(Config, "API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=getattr(Config, "API_PORT", 5000))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.web:
        from web.app import create_app
        create_app().run(host=args.host, port=args.port, debug=False)
    else:
        _configure_tcl_paths()
        from gui.main_window import MainWindow
        MainWindow().run()


if __name__ == "__main__":
    main()
