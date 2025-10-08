Análisis de microbiota con grafos esparsos y dinámica de osciladores

Este proyecto implementa un pipeline completo para estudiar la estructura de comunidades microbianas a partir de matrices de OTUs (~4 720 OTUs × 441 muestras en los datos proporcionados). A partir de las cuentas de OTUs se construyen varias vistas de similitud, se fusionan mediante un grafo esparso y se aplica un modelo de osciladores de Kuramoto para obtener afinidades de fase y clústeres comunitarios. La notebook resultante (analysis.ipynb) está estructurada en bloques independientes y puede adaptarse fácilmente a otros conjuntos de datos.

Flujo del pipeline (bloques 0–11)

Configuración – Importa las librerías principales (NumPy, SciPy, pandas, matplotlib) y trata de instalar silenciosamente paquetes opcionales como networkx, python‑louvain o igraph/leidenalg. Si no están disponibles, el código proporciona alternativas. Se definen semillas para reproducibilidad, las rutas de trabajo (Datos y Resultados) y los parámetros por defecto: número de vecinos TOPK=12, pesos de fusión (alpha=0.35, ppmi=0.45, clr=0.20), valores de K_g para el barrido logarítmico y argumentos por defecto para el simulador de Kuramoto y la afinidad de fase.

Autodescubrimiento del archivo OTU – Busca automáticamente el fichero de OTUs en el directorio ./Datos (*.otus, *otu*.tsv, *.csv, etc.). Si no encuentra ninguno, genera un conjunto sintético pequeño para permitir pruebas.

Lectura robusta de OTUs – Carga la matriz de OTUs con un heurístico para detectar el separador (coma o tabulador) y la orientación (OTUs como filas o como columnas). El código elimina la columna de taxonomía si aparece, agrupa OTUs duplicadas y garantiza que los identificadores de muestra son únicos. La matriz se almacena como scipy.sparse.csr_matrix para evitar densificar datos grandes.

Cálculo de diversidad alfa y similitud alfa – Para cada muestra se calcula la riqueza de especies, los índices de Shannon y de Simpson. Tras estandarizar (z‑score) estas métricas, se construye una matriz de similitud basada en el coseno y se extrae un grafo k‑NN (top‑k vecinos) sin densificar. Los nodos con diversidad alfa elevada aparecen como hubs en el grafo.

CLR y PPMI – Se generan dos vistas adicionales:

CLR (Centered Log‑Ratio): transforma las cuentas con un pseudo‑conteo, aplica logaritmo centrado y calcula una similitud coseno densa.

PPMI (Positive Pointwise Mutual Information): convierte las cuentas a proporciones, calcula expectativas de coocurrencia y aplica max(log2(p_ij / (p_i·p_j)), 0).
De cada vista se construye un grafo k‑NN esparso.

Fusión de vistas – Cada grafo se normaliza dividiendo sus pesos por W.data.max() (no se usa W.max() porque densificaría) y luego se combina con los pesos definidos en weights (alpha, ppmi, clr). La suma resultante se vuelve a esparcir con una rutina sparse_topk que extrae los TOPK vecinos mutuos. Se informa de la forma y del número de aristas del grafo fusionado.

Simulación de Kuramoto – El grafo fusionado se usa como red de acoplamiento en un modelo de Kuramoto discreto. Cada nodo es un oscilador cuya fase evoluciona según un esquema Heun/RK2 con paso dt, número de iteraciones T y un periodo de quemado (burn). Se normaliza por el grado para evitar dominancia de hubs. La salida es una matriz de fases (tiempo × muestras).

Afinidad de fase y clustering – La función phase_affinity calcula la afinidad entre pares de muestras mediante bloques, usando la identidad cos(Δ) = cos(θ_i)·cos(θ_j) + sin(θ_i)·sin(θ_j). Esta aproximación evita almacenar un tensor completo T × i × j. El grafo de afinidad se clusteriza:

Se intenta primero la heurística Louvain de python‑louvain si está disponible.

Si falla o el paquete no existe, se recurre a Label Propagation de networkx.

Como última opción, se usa una implementación propia de label propagation incluida en el bloque 8. Esta versión funciona directamente sobre matrices scipy.sparse y calcula la modularidad con una fórmula cerrada, de modo que no necesita networkx.
En todos los casos se comprueba que todos los nodos están presentes; si el grafo no contiene aristas se devuelve un único clúster.

Ejecución del experimento completo – Una función de alto nivel barre los valores de K_g dados en Kg_default_vals, ejecuta la simulación de Kuramoto, calcula afinidades, clusteriza y guarda los resultados. Se selecciona el K_g con mayor modularidad Q y se genera un resumen de la corrida. Los resultados se guardan en ./Resultados/:

labels.csv: asignación de muestras a clústeres.

grid_df.csv: tabla con K_g, modularidad Q, número de clústeres k y método de clustering.

alpha_metrics.csv: métricas de diversidad alfa por muestra.

run_summary.txt: resumen textual de la forma de la matriz, número de aristas, densidad, mejor K_g, mejor Q y número de clústeres. Si se activa ANONYMIZE_IDS, se genera además id_map.csv.

Visualizaciones – Se trazan dos figuras:

Curva Q vs K_g: ayuda a seleccionar el acoplamiento que maximiza la modularidad.

Grafo k‑NN por similitud alfa: los nodos se dibujan con un tamaño proporcional a la diversidad de Shannon. Si networkx no está disponible, se usa un embebido espectral a partir del laplaciano del grafo para posicionar los nodos en 2D. Esto evita depender de paquetes externos y mantiene el grafo esparso.

Estabilidad (opcional) – Un pequeño barrido de K_g y de alpha del modelo de Kuramoto calcula la estabilidad de las particiones mediante NMI (Normalized Mutual Information). Se muestra un mapa de calor y permite evaluar la robustez de los clústeres frente a cambios de parámetros.

Vistas y pesos de fusión
Vista	Descripción	Peso por defecto
Alpha	Utiliza la riqueza, Shannon y Simpson para caracterizar la diversidad interna de cada muestra. La similitud se calcula con el coseno entre vectores z‑score.	0.35
PPMI	Mide la co‑ocurrencia de OTUs tras convertir las cuentas a proporciones. Destaca pares de OTUs que aparecen juntos más de lo esperado por azar.	0.45
CLR	Aplica una transformación log‑ratio centrada para comparar abundancias relativas. Es sensible a cambios en OTUs dominantes.	0.20

Los pesos se pueden ajustar en el primer bloque (weights). Aumentar el peso de alpha enfatiza la diversidad general de cada muestra (muestras con índices de Shannon similares se conectarán más). Incrementar el peso de PPMI refuerza las relaciones de co‑ocurrencia raras, mientras que un mayor peso de CLR prioriza semejanzas en abundancias relativas. Cambiar estos parámetros altera las aristas del grafo fusionado y, por tanto, la dinámica de Kuramoto y los clústeres resultantes.

Ajuste de parámetros

TOPK (topk): número de vecinos en el grafo de cada vista y en la fusión. Valores pequeños producen grafos más esparsos; valores mayores aumentan la conectividad y el tiempo de cómputo.

Kg_default_vals: vector de valores de acoplamiento K_g a explorar (geométrico entre 0.7 y 1.8 por defecto). Puede modificarse para investigar otras regiones de la dinámica.

kuramoto_defaults: incluye dt, T, burn, alpha y normalize_by_degree. Disminuir T reduce el tiempo de simulación pero puede afectar la convergencia; aumentar burn descarta más iteraciones iniciales.

phase_affinity_defaults: stride controla el submuestreo temporal y chunk_n el tamaño de bloque de columnas para calcular afinidades; reducirlos ahorra memoria a costa de precisión.

ANONYMIZE_IDS: si se activa (True), los identificadores de muestra se reemplazan por etiquetas anónimas (sampleXXXX) en las salidas y se guarda un mapa en id_map.csv.

Ejecución

Copie los archivos de datos (por ejemplo otu_data.otus) en el directorio ./Datos junto a la notebook.

Abra analysis.ipynb y ejecute las celdas en orden. La celda de instalación intentará descargar networkx, python‑louvain y python‑igraph silenciosamente; si falla, el código seguirá funcionando mediante las implementaciones de respaldo incluidas.

Ajuste los parámetros de interés (TOPK, pesos, valores de K_g, etc.) en el bloque 1 antes de ejecutar el experimento completo.

Ejecute el bloque 9 para lanzar el experimento y generar los CSV en ./Resultados. El resumen de la corrida se imprimirá en la consola y se guardará en run_summary.txt.

Use el bloque 10 para visualizar la curva Q vs K_g y el grafo por similitud alfa. El grafo utiliza un embebido espectral si networkx no está instalado.

(Opcional) Ejecute el bloque 11 para evaluar la estabilidad de las particiones mediante NMI en una rejilla ligera de parámetros.

Salidas y contenido de ./Resultados

Tras una corrida típica se generan los siguientes archivos en el directorio Resultados:

Archivo	Descripción
labels.csv	Tabla con dos columnas (sample_id, cluster) que asigna a cada muestra su clúster final según la mejor modularidad Q.
grid_df.csv	Resultados del barrido de K_g: incluye K_g, la modularidad Q, el número de clústeres k y el método de clustering usado.
alpha_metrics.csv	Métricas alfa por muestra (riqueza, Shannon, Simpson) y sus versiones z‑score.
run_summary.txt	Resumen humano‑legible con la forma de la matriz OTU, TOPK, número de aristas y densidad del grafo fusionado, el mejor K_g, la mejor modularidad Q, el número de clústeres y el método empleado.
id_map.csv (opcional)	Mapeo entre identificadores de muestra originales y anónimos cuando ANONYMIZE_IDS=True.
Consejos de rendimiento

Mantener las matrices esparsas: nunca convierta los grafos a matrices densas con .toarray(); todas las operaciones de top‑k y fusiones usan estructuras CSR para evitar exceder la memoria de 16 GB.

Tamaño de TOPK: un TOPK pequeño reduce los tiempos de construcción y fusión de grafos, pero puede fragmentar la red; experimente con valores entre 8 y 20 según la complejidad de los datos.

Simulaciones de Kuramoto: los parámetros T, burn y dt afectan el tiempo total. Para ensayos rápidos puede reducir T (p. ej. 800) y ajustar burn proporcionalmente, aunque la estabilidad de fase puede disminuir.

Uso de CPU: la implementación utiliza operaciones vectorizadas en NumPy y SciPy; asegúrese de ejecutar la notebook en un entorno que aproveche la arquitectura (por ejemplo, MKL).

Dependencias opcionales: si dispone de acceso a internet, instalar networkx y python‑louvain acelera el clustering y facilita las visualizaciones. De lo contrario, las implementaciones incluidas garantizan que el pipeline se ejecute correctamente.

En resumen, este proyecto ofrece una plataforma modular para explorar la estructura de comunidades microbianas mediante grafos esparsos y dinámica de osciladores. Ajustando los pesos y parámetros podrá investigar cómo distintos aspectos de la diversidad y co‑ocurrencia influyen en las redes y sus clústeres.
