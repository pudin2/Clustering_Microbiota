# Estructura del proyecto

La lógica funcional vive en `modules/`. Cada módulo es ahora un paquete Python independiente con su propio `__init__.py`.

```text
Libreria_Python_reorganizada/
├── modules/
│   ├── load/
│   ├── characterization/
│   ├── create_df/
│   ├── dbscan/
│   ├── exploration/
│   ├── visualizations/      # extraído de Exploration.py
│   ├── kde/
│   ├── kruskal_wallis/
│   ├── mann_whitney/
│   ├── math_agent/
│   ├── odds_ratio/
│   └── smart_assistant/
├── gui_app.py
├── web_app.py
├── run_gui.py
├── main.py
├── requirements.txt
└── tests y scripts auxiliares
```

## Cambio principal

`visualization_from_loaded` ya no está dentro de `Exploration.py`. Ahora vive en:

`modules/visualizations/visualizations.py`

La GUI importa este módulo directamente:

```python
from modules.visualizations import visualization_from_loaded
```

Los demás archivos de lógica también pasaron de ser archivos sueltos en la raíz a paquetes dentro de `modules/`.
