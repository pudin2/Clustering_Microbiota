# Clustering Microbiota

Workbench estadistico para cargar datasets de microbiota, explorar variables,
ejecutar pruebas, revisar resultados y construir visualizaciones.

## Que se mejoro

Esta version agrega una capa de interfaz mas amable para usuarios nuevos y
mantiene la aplicacion original de escritorio para pruebas comparativas.

- Nueva pestana **Asistente** dentro de la GUI.
- Ayudas con icono `!` en botones y campos para explicar que hace cada control.
- Motor local de recomendaciones que interpreta preguntas en lenguaje natural.
- Integracion opcional con modelos abiertos via Ollama local.
- Paneles nuevos para exploracion, correlacion, visualizaciones, reduccion de
  dimensionalidad y revision de clusters.
- Constructor visual para solapar capas de graficas, como puntos, tendencia,
  densidad, centroides y escalas logaritmicas.
- Prototipo web paralelo para probar una interfaz mas interactiva sin romper la
  version Tkinter.

## Como ejecutar

Aplicacion de escritorio:

```powershell
python Libreria_Python\run_gui.py
```

Prototipo web local:

```powershell
python Libreria_Python\web_app.py
```

Luego abrir:

```text
http://127.0.0.1:8765
```

## Asistente estadistico

El asistente funciona en dos modos:

- **Local por reglas**: no requiere internet ni modelo externo. Lee los datasets
  cargados, detecta tipos de columnas, sugiere pruebas y llena parametros.
- **Ollama opcional**: si Ollama esta corriendo en la maquina, puede usar un
  modelo abierto local, por ejemplo `qwen2.5:3b`, para generar explicaciones mas
  conversacionales. Si Ollama no responde, la app conserva la recomendacion local.

Ejemplos de preguntas:

```text
Quiero comparar glucosa entre grupos de sexo.
Quiero revisar presion por sexo.
Necesito una correlacion entre HDL, LDL y trigliceridos.
Quiero graficar rank abundancia de OTUs.
Analiza los resultados de la ultima corrida.
```

## Flujo recomendado

1. Cargar datasets desde la barra lateral.
2. Entrar a **Asistente** y preguntar que prueba conviene.
3. Revisar la respuesta y usar **Aplicar sugerencias**.
4. Ir a la pestana sugerida, revisar campos y ejecutar.
5. Explorar tablas, figuras y HTML interactivos en **Resultados**.
6. Usar **Visualizaciones** para construir graficas comparativas por capas.

## Archivos principales

- `Libreria_Python/gui_app.py`: interfaz Tkinter principal.
- `Libreria_Python/Smart_Assistant.py`: asistente local y conexion opcional a Ollama.
- `Libreria_Python/Exploration.py`: exploracion, correlacion, graficas,
  dimensionalidad y revision de clusterizacion.
- `Libreria_Python/web_app.py`: prototipo web local.
- `outputs_gui/`: carpeta ignorada por Git donde se guardan corridas y artefactos.

Mas detalles tecnicos en `docs/NUEVAS_INTEGRACIONES.md`.
