# Arquitectura de agentes

## Orquestador bioestadístico
Recibe la pregunta, selecciona el dataset, consulta el inspector y consolida la respuesta final.

## Agente de diseño de estudio
Busca información sobre independencia, pareamiento, longitudinalidad, outcome, exposición, covariables, unidad experimental y objetivo inferencial.

## Agente de calidad y supuestos
Revisa faltantes, tamaños de grupo, valores constantes, ceros, distribución, independencia, composicionalidad y potenciales sesgos.

## Agente selector de pruebas
Contrasta la propuesta determinística con alternativas paramétricas, no paramétricas, categóricas, correlacionales, multivariadas y de clustering disponibles en el proyecto.

## Agente de parámetros y multiplicidad
Sugiere alfa, alternativa, tamaños mínimos, FDR, pseudocount, transformación, escalado, componentes, `eps`, `min_samples` y diagnósticos.

## Agente de interpretación
Explica efecto, incertidumbre, significancia, límites de causalidad, multiplicidad y forma responsable de reportar resultados.

Actualmente estos roles se ejecutan como un panel coordinado dentro de una sola llamada para reducir latencia y costo. La interfaz está preparada para separar llamadas por agente en una evolución posterior.
