# BioInsight Health Lab — frontend por componentes

Proyecto Angular 17 reorganizado por páginas, layout, modelos y servicio de estado.

## Ejecutar

```bash
npm install
npm start
```

Abrir `http://localhost:4200`.

## Estructura principal

- `layout/sidebar` y `layout/topbar`
- `pages/home`
- `pages/datasets`
- `pages/analysis`
- `pages/assistant`
- `pages/results`
- `services/workbench-state.service.ts`
- `models/app.models.ts`

El frontend conserva el comportamiento de demostración. El siguiente ajuste debe hacerse directamente en `pages/analysis` y `pages/results`, sin volver a concentrar código en `app.component`.
