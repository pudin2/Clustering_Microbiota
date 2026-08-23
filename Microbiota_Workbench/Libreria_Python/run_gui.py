from pathlib import Path
import sys


# Los módulos de la aplicación viven en la misma carpeta que este lanzador.
LIB_DIR = Path(__file__).resolve().parent
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from gui_app import main


if __name__ == "__main__":
    main()
