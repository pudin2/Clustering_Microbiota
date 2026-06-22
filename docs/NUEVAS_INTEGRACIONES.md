# Nuevas integraciones de interfaz y asistente

Este documento resume la mejora reciente de la herramienta para que cualquier
persona pueda entender que cambio, como usarlo y donde esta implementado.

## Objetivo de la mejora

La interfaz previa era funcional, pero exigia que el usuario supiera de antemano
que prueba ejecutar y que parametros llenar. La mejora busca convertir la app en
una herramienta guiada:

- El usuario puede preguntar en lenguaje natural.
- La app sugiere pruebas y parametros segun los tipos de datos cargados.
- Cada boton/campo tiene ayuda contextual con `!`.
- Las graficas se pueden construir visualmente por capas.
- La version antigua de escritorio se mantiene y se suma un prototipo web
  paralelo para pruebas.

## Componentes agregados

### 1. Asistente local

Archivo: `Libreria_Python/Smart_Assistant.py`

Responsabilidades:

- Inspeccionar datasets cargados.
- Separar columnas numericas, categoricas, mixtas e identificadores.
- Detectar matrices de abundancia probables.
- Interpretar intenciones como comparar grupos, correlacionar variables,
  preprocesar, graficar, revisar normalidad, ejecutar KDE o preparar DBSCAN.
- Producir un objeto de respuesta con texto, advertencias y parametros
  aplicables a la GUI.
- Conectarse opcionalmente a Ollama local.

El asistente no depende de un servicio externo para funcionar. La capa de Ollama
solo mejora la explicacion cuando el usuario la activa.

### 2. Pestana Asistente en la GUI

Archivo: `Libreria_Python/gui_app.py`

Ubicacion principal:

- `_build_assistant_tab`
- `ask_assistant`
- `ask_assistant_dataset_summary`
- `apply_assistant_suggestions`
- `_assistant_results_response`

Funciones para el usuario:

- Elegir dataset.
- Escribir una pregunta en lenguaje natural.
- Pedir resumen de datasets.
- Activar Ollama local si esta disponible.
- Aplicar parametros sugeridos a la pestana correspondiente.
- Pedir una lectura basica de resultados ya ejecutados.

### 3. Ayudas de interfaz

Archivo: `Libreria_Python/gui_app.py`

Se agrego un sistema de mensajes con icono `!` para que los usuarios entiendan:

- Que hace cada boton.
- Que tipo de dato espera cada campo.
- Que revisar antes de ejecutar una prueba.

Esto apunta a que la herramienta sea usable por personas que no conocen todos
los detalles estadisticos de entrada.

### 4. Modulo de exploracion y visualizacion

Archivo: `Libreria_Python/Exploration.py`

Funciones principales:

- `dataset_profile_from_loaded`
- `correlation_from_loaded`
- `visualization_from_loaded`
- `dimensionality_from_loaded`
- `cluster_review_from_loaded`

Capacidades:

- Perfil de datasets y columnas.
- Separacion de columnas numericas/no numericas.
- Heuristicas de continuidad.
- Estimacion de bins para histogramas.
- Correlacion Pearson y Spearman con matriz y p-valores.
- Comparacion de significancias con FDR y Bonferroni.
- Graficas conjuntas, violin plots y rank-abundancia.
- HTML interactivo cuando Plotly esta disponible.
- Reduccion de dimensionalidad fuera de DBSCAN.
- Revision de metricas y criterios de clusterizacion.

### 5. Constructor visual por capas

Archivo: `Libreria_Python/gui_app.py`

Ubicacion principal:

- `_build_visualization_tab`
- `update_visual_builder`
- `save_visual_builder_result`

Permite construir una grafica marcando capas:

- Puntos.
- Linea.
- Tendencia.
- Densidad.
- Centroides por grupo.
- Log X / Log Y.
- Opacidad y tamano de puntos.

La grafica se puede guardar como corrida normal, con manifiesto y figura.

### 6. Prototipo web paralelo

Archivo: `Libreria_Python/web_app.py`

El prototipo web usa solo librerias estandar de Python para evitar agregar una
dependencia fuerte en esta etapa. Sirve una pagina local con:

- Lista de datasets en `Datos/`.
- Pregunta al asistente.
- Resumen de parametros sugeridos.
- Opcion para Ollama local.

Ejecucion:

```powershell
python Libreria_Python\web_app.py
```

URL:

```text
http://127.0.0.1:8765
```

## Integracion con Ollama

La integracion espera que Ollama este levantado en:

```text
http://localhost:11434/api/generate
```

Modelo sugerido por defecto:

```text
qwen2.5:3b
```

Si Ollama no esta disponible, el asistente agrega un aviso y conserva la
recomendacion local basada en reglas.

## Resultado esperado para usuarios nuevos

Antes, el usuario tenia que saber que analisis elegir y como parametrizarlo.
Ahora puede empezar con preguntas como:

```text
Tengo una variable de glucosa y quiero compararla por sexo.
Tengo OTUs y quiero una grafica de rank abundancia.
No se si debo usar Pearson o Spearman.
Que hago antes de correr DBSCAN?
Analiza la ultima corrida.
```

La app responde con una guia y puede llenar automaticamente los campos
correspondientes para que el usuario revise y ejecute.

## Validacion rapida

Comandos usados para validar:

```powershell
python -B -c "import ast, pathlib; files=['Libreria_Python/Smart_Assistant.py','Libreria_Python/web_app.py','Libreria_Python/Exploration.py','Libreria_Python/gui_app.py']; [ast.parse(pathlib.Path(f).read_text(encoding='utf-8-sig'), filename=f) for f in files]; print('ast_ok')"
python -B -c "import sys; sys.path.insert(0, r'Libreria_Python'); import gui_app, web_app, Smart_Assistant; print('imports_ok')"
```

Tambien se valido el endpoint local:

```text
GET  /api/datasets
POST /api/ask
```
