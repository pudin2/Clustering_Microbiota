from pathlib import Path
import sys


LIB_DIR = Path(__file__).resolve().parent / "Libreria_Python"
sys.path.insert(0, str(LIB_DIR))

from gui_app import main


if __name__ == "__main__":
    main()
