# Microbiota Workbench — Angular + Python

Esta versión reemplaza el frontend Python por el frontend Angular y conserva los módulos estadísticos de Python como backend.

## Arquitectura

```text
Angular (puerto 4200 en desarrollo)
        │
        │ /api/*
        ▼
Python API (puerto 8765)
        │
        ├── modules/load
        ├── modules/exploration
        ├── modules/characterization
        ├── modules/visualizations
        ├── modules/kde
        ├── modules/kruskal_wallis
        ├── modules/mann_whitney
        ├── modules/dbscan
        └── modules/smart_assistant
```

## Qué quedó conectado

- Datasets reales del backend, sin datos simulados en Angular.
- Carga de archivos CSV/TSV/TXT/OTUS/META/TAXONOMY desde Angular.
- Columnas y categorías detectadas en Python y usadas por los formularios Angular.
- Asistente Angular conectado a `OpenAssistantEngine`.
- Ejecución real de Exploración, Caracterización, Normalidad, Correlación, Visualizaciones, KDE, Kruskal-Wallis, Mann-Whitney, Reducción/PCA, DBSCAN y Revisión de clusters.
- Historial de corridas.
- Tablas y figuras generadas por Python visibles desde la página Resultados.

## Primera ejecución en Windows

### 1. Backend Python

Desde la carpeta raíz:

```bat
cd Libreria_Python
python -m pip install -r requirements.txt
python api_server.py
```

El backend queda en `http://127.0.0.1:8765`.

### 2. Frontend Angular en desarrollo

En otra terminal:

```bat
cd microbiota-health-angular
rmdir /s /q node_modules 2>nul
npm install
npm start
```

Abre `http://localhost:4200`.

`npm start` usa `proxy.conf.json`, por lo que `/api` se redirige automáticamente al backend Python.

## Ejecutar como una sola aplicación

Compila Angular:

```bat
cd microbiota-health-angular
npm install
npm run build
```

Luego inicia Python:

```bat
cd ..\Libreria_Python
python api_server.py
```

Después abre `http://127.0.0.1:8765`. El mismo servidor Python sirve el Angular compilado y la API.

## Archivos principales de la integración

- `Libreria_Python/api_server.py`: API REST y servidor del Angular compilado.
- `microbiota-health-angular/src/app/services/workbench-state.service.ts`: comunicación Angular ↔ Python.
- `microbiota-health-angular/proxy.conf.json`: proxy de desarrollo.
- `microbiota-health-angular/src/app/pages/analysis/analysis.component.ts`: ejecución real de análisis.
- `microbiota-health-angular/src/app/pages/results/`: visualización de resultados reales.
- `microbiota-health-angular/src/app/pages/datasets/`: carga de datasets reales.

## Endpoints principales

- `GET /api/health`
- `GET /api/datasets`
- `POST /api/datasets/upload`
- `POST /api/ask`
- `POST /api/analyze`
- `POST /api/run`
- `GET /api/runs`
- `GET /api/runs/{id}`
- `GET /api/runs/{id}/files/{archivo}`

## Nota sobre el ZIP original

El `node_modules` recibido originalmente fue instalado en Windows. No se incluye en esta entrega integrada porque debe regenerarse en el equipo donde se ejecute con `npm install`.
