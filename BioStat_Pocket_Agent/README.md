# BioStat Pocket Agent

Asistente de bioestadística para investigaciones clínicas, nutricionales y de microbiota. Combina un motor determinístico que inspecciona el dataset y configura análisis con una revisión de Qwen 3.5 9B en cloud o mediante Ollama local.

## Qué cambió

- Tres motores seleccionables: `cloud`, `local` y `rules`.
- Cloud como opción predeterminada para no depender del hardware del computador.
- Modelo predeterminado cloud: `qwen3.5-9b` (el identificador se puede cambiar según el proveedor).
- Modelo local sugerido: `qwen3.5:9b` en Ollama.
- Panel virtual de cinco agentes: diseño de estudio, calidad/supuestos, selección de pruebas, parámetros/multiplicidad e interpretación científica.
- La salida del LLM complementa, no reemplaza, la recomendación determinística.
- Si cloud u Ollama fallan, la aplicación continúa con reglas locales.
- Se envían al cloud resúmenes estructurados, nombres de columnas y conteos; no se envía automáticamente el dataset completo.

## Configuración cloud

1. Copia `.env.example` como `.env`.
2. Escribe tu API key en `QWEN_CLOUD_API_KEY`.
3. Confirma en tu proveedor el endpoint y el identificador exacto del modelo. El proyecto utiliza una API compatible con OpenAI Chat Completions.
4. En la pestaña **Asistente**, selecciona `cloud`.

Variables:

```env
QWEN_CLOUD_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_CLOUD_API_KEY=tu_clave
QWEN_CLOUD_MODEL=qwen3.5-9b
```

La clave nunca debe escribirse dentro del código ni subirse a Git.

## Configuración local

1. Instala Ollama.
2. Descarga el modelo disponible en tu instalación, por ejemplo:

```powershell
ollama pull qwen3.5:9b
```

3. Selecciona `local` y usa el nombre exacto mostrado por `ollama list`.

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run_gui.py
```

Para la interfaz web:

```powershell
python web_app.py
```

Después abre la dirección indicada en consola.

## Flujo del agente

1. Inspecciona tipos, faltantes, cardinalidad, ceros y posible estructura de abundancias.
2. El motor determinístico propone una prueba y llena parámetros compatibles con las pestañas de la aplicación.
3. Qwen revisa la propuesta como un panel de especialistas.
4. La respuesta separa recomendación, justificación, parámetros, verificaciones, interpretación y limitaciones.
5. El investigador revisa y ejecuta la prueba; el agente no sustituye el criterio científico ni el protocolo del estudio.

## Privacidad

En modo cloud se transmiten al proveedor la pregunta y un perfil resumido del dataset. No se envían todas las filas de forma predeterminada. Para datos sensibles o identificables, anonimiza columnas y revisa las condiciones del proveedor antes de usar cloud. El modo `local` mantiene la inferencia en la máquina donde corre Ollama.

## Nota sobre el nombre del modelo

Los proveedores pueden publicar Qwen 3.5 9B con identificadores distintos. Cambia `QWEN_CLOUD_MODEL` o el campo **Modelo** sin modificar el código.
