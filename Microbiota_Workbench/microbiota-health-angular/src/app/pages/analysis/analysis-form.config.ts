import {
  AnalysisFormConfig
} from './analysis-form.models';

/**
 * Configuración central de todos los formularios.
 *
 * Exploración conserva su formulario especializado.
 * Los demás análisis se construyen dinámicamente con este objeto.
 */
export const ANALYSIS_FORMS: Record<
  string,
  AnalysisFormConfig
> = {

  /* =======================================================
     CARACTERIZACIÓN
  ======================================================= */

  characterization: {
    analysisKey: 'characterization',

    title: 'Configurar caracterización',
    description:
      'Genera resúmenes descriptivos e histogramas para conocer la distribución general de las variables.',

    actionLabel: 'Ejecutar caracterización',
    runningLabel: 'Ejecutando caracterización…',

    recommendationTitle:
      'Preparación recomendada',

    recommendationText:
      'Selecciona variables numéricas relevantes. Si no eliges columnas específicas, se utilizarán todas las variables numéricas disponibles.',

    sections: [
      {
        key: 'characterization-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Parámetros descriptivos',
        description:
          'Selecciona el dataset, las variables y la forma en que se construirán los resúmenes.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset principal',
            type: 'dataset',
            help:
              'Archivo que contiene las variables que deseas caracterizar.',
            description:
              'Fuente principal del análisis descriptivo.',
            defaultValue: '',
            required: true
          },
          {
            key: 'variables',
            label: 'Columnas numéricas',
            type: 'variables',
            help:
              'Variables numéricas que se incluirán en los resúmenes y gráficos.',
            description:
              'Selecciona algunas variables o utiliza todas las columnas numéricas.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'mode',
            label: 'Modo de análisis',
            type: 'select',
            help:
              'Define si el análisis se realiza por columna, sobre la matriz completa o de ambas maneras.',
            defaultValue: 'both',
            options: [
              {
                value: 'by_column',
                label: 'Por columna',
                description:
                  'Analiza cada variable individualmente.'
              },
              {
                value: 'full_matrix',
                label: 'Matriz completa',
                description:
                  'Analiza todos los valores como un conjunto.'
              },
              {
                value: 'both',
                label: 'Ambos',
                description:
                  'Genera análisis por columna y de matriz completa.'
              }
            ]
          },
          {
            key: 'bins',
            label: 'Número de bins',
            type: 'number',
            help:
              'Cantidad de intervalos utilizados para construir los histogramas.',
            description:
              'Un valor mayor produce más detalle en la distribución.',
            defaultValue: 80,
            min: 5,
            max: 500,
            step: 1
          },
          {
            key: 'positiveOnly',
            label: 'Graficar solo valores positivos',
            type: 'boolean',
            help:
              'Excluye ceros y valores negativos de los histogramas positivos.',
            description:
              'Útil para datos de abundancia o concentraciones.',
            defaultValue: true
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye en los resultados un resumen general del procesamiento.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     NORMALIDAD
  ======================================================= */

  normality: {
    analysisKey: 'normality',

    title: 'Configurar análisis de normalidad',
    description:
      'Evalúa los supuestos de distribución de las variables numéricas mediante pruebas estadísticas.',

    actionLabel: 'Ejecutar normalidad',
    runningLabel: 'Evaluando normalidad…',

    recommendationTitle:
      'Interpretación metodológica',

    recommendationText:
      'Las pruebas de normalidad deben interpretarse junto con histogramas, gráficos Q-Q y tamaño de muestra. Un p-valor bajo no describe por sí solo la magnitud de la desviación.',

    sections: [
      {
        key: 'normality-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Variables y pruebas',
        description:
          'Selecciona qué variables, valores y métodos se utilizarán.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset principal',
            type: 'dataset',
            help:
              'Dataset que contiene las variables numéricas que serán evaluadas.',
            defaultValue: '',
            required: true
          },
          {
            key: 'variables',
            label: 'Columnas numéricas',
            type: 'variables',
            help:
              'Variables numéricas sobre las que se ejecutarán las pruebas.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'mode',
            label: 'Modo de análisis',
            type: 'select',
            help:
              'Determina si las pruebas se ejecutan por variable, sobre todos los valores o de ambas formas.',
            defaultValue: 'both',
            options: [
              {
                value: 'by_column',
                label: 'Por columna'
              },
              {
                value: 'full_matrix',
                label: 'Matriz completa'
              },
              {
                value: 'both',
                label: 'Ambos'
              }
            ]
          },
          {
            key: 'valueMode',
            label: 'Valores incluidos',
            type: 'select',
            help:
              'Permite evaluar todos los valores, solamente los positivos o ambos escenarios.',
            defaultValue: 'both',
            options: [
              {
                value: 'all',
                label: 'Todos los valores'
              },
              {
                value: 'positive',
                label: 'Solo valores positivos'
              },
              {
                value: 'both',
                label: 'Ambos escenarios'
              }
            ]
          },
          {
            key: 'testMethod',
            label: 'Prueba estadística',
            type: 'select',
            help:
              'Selecciona el método utilizado para evaluar la normalidad.',
            defaultValue: 'both',
            options: [
              {
                value: 'shapiro',
                label: 'Shapiro-Wilk'
              },
              {
                value: 'anderson',
                label: 'Anderson-Darling'
              },
              {
                value: 'both',
                label: 'Ejecutar ambas'
              }
            ]
          },
          {
            key: 'alpha',
            label: 'Nivel de significancia',
            type: 'number',
            help:
              'Umbral utilizado para interpretar el resultado de la prueba.',
            description:
              'El valor convencional para análisis exploratorios es 0.05.',
            defaultValue: 0.05,
            min: 0.001,
            max: 1,
            step: 0.001
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Agrega al resultado un resumen de las pruebas realizadas.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     CORRELACIÓN
  ======================================================= */

  correlation: {
    analysisKey: 'correlation',

    title: 'Configurar correlaciones',
    description:
      'Calcula asociaciones lineales y monotónicas mediante Pearson y Spearman.',

    actionLabel: 'Calcular correlaciones',
    runningLabel: 'Calculando correlaciones…',

    recommendationTitle:
      'Lectura responsable',

    recommendationText:
      'Una correlación no implica causalidad. Revisa también los p-valores ajustados, el tamaño de muestra y los gráficos de dispersión.',

    sections: [
      {
        key: 'correlation-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Pearson y Spearman',
        description:
          'Selecciona variables y criterios mínimos para construir las matrices de correlación.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset principal',
            type: 'dataset',
            help:
              'Archivo que contiene las variables numéricas del análisis.',
            defaultValue: '',
            required: true
          },
          {
            key: 'variables',
            label: 'Variables',
            type: 'variables',
            help:
              'Variables numéricas que se incluirán en las matrices de Pearson y Spearman.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'alpha',
            label: 'Nivel de significancia',
            type: 'number',
            help:
              'Umbral utilizado para evaluar la significancia estadística.',
            defaultValue: 0.05,
            min: 0.001,
            max: 1,
            step: 0.001
          },
          {
            key: 'minNonNull',
            label: 'Mínimo de datos válidos',
            type: 'number',
            help:
              'Cantidad mínima de observaciones no faltantes para calcular una correlación.',
            defaultValue: 3,
            min: 2,
            step: 1
          },
          {
            key: 'maxPlotVariables',
            label: 'Máximo de variables en heatmap',
            type: 'number',
            help:
              'Número máximo de variables que se mostrarán en el mapa de calor.',
            defaultValue: 25,
            min: 2,
            max: 200,
            step: 1
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye información general de las correlaciones calculadas.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     VISUALIZACIONES
  ======================================================= */

  visualization: {
    analysisKey: 'visualization',

    title: 'Configurar visualizaciones',
    description:
      'Construye gráficos conjuntos, violines, rank-abundancia y composiciones visuales personalizadas.',

    actionLabel: 'Generar visualizaciones',
    runningLabel: 'Generando visualizaciones…',

    recommendationTitle:
      'Construcción visual',

    recommendationText:
      'Selecciona variables compatibles con cada gráfico. Las variables numéricas funcionan como ejes y las categóricas como grupos o colores.',

    previewType: 'visual-builder',

    sections: [
      {
        key: 'joint-variables',
        eyebrow: 'GRÁFICOS CONJUNTOS',
        title: 'Variables principales',
        description:
          'Configura los ejes y la agrupación de los gráficos conjuntos.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset principal',
            type: 'dataset',
            help:
              'Dataset utilizado para todas las visualizaciones.',
            defaultValue: '',
            required: true
          },
          {
            key: 'xColumn',
            label: 'Variable del eje X',
            type: 'column',
            help:
              'Variable que se ubicará en el eje horizontal.',
            defaultValue: '',
            datasetKey: 'dataset'
          },
          {
            key: 'yColumn',
            label: 'Variable del eje Y',
            type: 'column',
            help:
              'Variable que se ubicará en el eje vertical.',
            defaultValue: '',
            datasetKey: 'dataset'
          },
          {
            key: 'colorColumn',
            label: 'Variable de color',
            type: 'column',
            help:
              'Variable opcional utilizada para diferenciar grupos por color.',
            defaultValue: '',
            datasetKey: 'dataset'
          }
        ]
      },
      {
        key: 'violin-plots',
        eyebrow: 'DISTRIBUCIONES',
        title: 'Gráficos de violín',
        description:
          'Compara la distribución de variables numéricas entre grupos.',

        fields: [
          {
            key: 'violinGroup',
            label: 'Columna de grupo',
            type: 'column',
            help:
              'Variable categórica utilizada para dividir las distribuciones.',
            defaultValue: '',
            datasetKey: 'dataset'
          },
          {
            key: 'violinVariables',
            label: 'Variables numéricas',
            type: 'variables',
            help:
              'Variables que se representarán mediante gráficos de violín.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: false
          }
        ]
      },
      {
        key: 'rank-abundance',
        eyebrow: 'MICROBIOTA',
        title: 'Rank-abundancia',
        description:
          'Configura una curva de abundancia ordenada para features u OTUs.',

        fields: [
          {
            key: 'rankAbundanceEnabled',
            label: 'Generar rank-abundancia',
            type: 'boolean',
            help:
              'Activa la generación del gráfico de rank-abundancia.',
            defaultValue: false
          },
          {
            key: 'abundanceId',
            label: 'Columna de identificación',
            type: 'column',
            help:
              'Columna identificadora que no debe tratarse como abundancia.',
            defaultValue: '',
            datasetKey: 'dataset',
            visibleWhen: {
              field: 'rankAbundanceEnabled',
              equals: true
            }
          },
          {
            key: 'abundanceColumns',
            label: 'Columnas de abundancia',
            type: 'variables',
            help:
              'Features numéricos utilizados para construir la curva.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: true,
            visibleWhen: {
              field: 'rankAbundanceEnabled',
              equals: true
            }
          },
          {
            key: 'topN',
            label: 'Top N',
            type: 'number',
            help:
              'Cantidad máxima de features que se mostrarán.',
            defaultValue: 2000,
            min: 1,
            step: 1,
            visibleWhen: {
              field: 'rankAbundanceEnabled',
              equals: true
            }
          },
          {
            key: 'logScale',
            label: 'Usar escala logarítmica',
            type: 'boolean',
            help:
              'Facilita la visualización cuando existen diferencias grandes de abundancia.',
            defaultValue: true,
            visibleWhen: {
              field: 'rankAbundanceEnabled',
              equals: true
            }
          }
        ]
      },
      {
        key: 'visual-builder',
        eyebrow: 'CONSTRUCTOR',
        title: 'Capas visuales',
        description:
          'Combina puntos, líneas, tendencias, densidades y centroides.',

        fields: [
          {
            key: 'layerScatter',
            label: 'Mostrar puntos',
            type: 'boolean',
            help:
              'Dibuja las observaciones individuales.',
            defaultValue: true
          },
          {
            key: 'layerLine',
            label: 'Mostrar línea',
            type: 'boolean',
            help:
              'Une las observaciones ordenadas por la variable X.',
            defaultValue: false
          },
          {
            key: 'layerTrend',
            label: 'Mostrar tendencia',
            type: 'boolean',
            help:
              'Agrega una línea de tendencia general.',
            defaultValue: true
          },
          {
            key: 'layerDensity',
            label: 'Mostrar densidad',
            type: 'boolean',
            help:
              'Agrega una capa de densidad debajo de los puntos.',
            defaultValue: false
          },
          {
            key: 'layerCentroids',
            label: 'Mostrar centroides',
            type: 'boolean',
            help:
              'Marca los promedios de cada grupo.',
            defaultValue: true
          },
          {
            key: 'logX',
            label: 'Escala logarítmica en X',
            type: 'boolean',
            help:
              'Transforma visualmente el eje X a escala logarítmica.',
            defaultValue: false
          },
          {
            key: 'logY',
            label: 'Escala logarítmica en Y',
            type: 'boolean',
            help:
              'Transforma visualmente el eje Y a escala logarítmica.',
            defaultValue: false
          },
          {
            key: 'pointOpacity',
            label: 'Opacidad de los puntos',
            type: 'number',
            help:
              'Controla la transparencia de los puntos entre 0 y 1.',
            defaultValue: 0.75,
            min: 0,
            max: 1,
            step: 0.05
          },
          {
            key: 'pointSize',
            label: 'Tamaño de los puntos',
            type: 'number',
            help:
              'Define el tamaño visual de cada observación.',
            defaultValue: 34,
            min: 1,
            max: 300,
            step: 1
          }
        ]
      }
    ]
  },


  /* =======================================================
     KDE
  ======================================================= */

  kde: {
    analysisKey: 'kde',

    title: 'Configurar estimación KDE',
    description:
      'Estima distribuciones de densidad y compara kernels y bandwidths.',

    actionLabel: 'Ejecutar KDE',
    runningLabel: 'Calculando densidades…',

    recommendationTitle:
      'Selección del bandwidth',

    recommendationText:
      'El bandwidth controla el nivel de suavizado. Valores muy pequeños generan curvas inestables y valores altos pueden ocultar estructuras relevantes.',

    sections: [
      {
        key: 'kde-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Parámetros de densidad',
        description:
          'Configura la validación cruzada y la búsqueda del bandwidth.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset OTU',
            type: 'dataset',
            help:
              'Dataset que contiene las variables de abundancia.',
            defaultValue: '',
            required: true
          },
          {
            key: 'gridSize',
            label: 'Tamaño de la cuadrícula',
            type: 'number',
            help:
              'Cantidad de puntos utilizados para evaluar la función de densidad.',
            defaultValue: 512,
            min: 50,
            step: 1
          },
          {
            key: 'cvSubsample',
            label: 'Submuestra para validación',
            type: 'number',
            help:
              'Número máximo de observaciones utilizadas en la validación cruzada.',
            defaultValue: 2000,
            min: 10,
            step: 1
          },
          {
            key: 'cvFolds',
            label: 'Particiones de validación',
            type: 'number',
            help:
              'Número de particiones utilizadas en la validación cruzada.',
            defaultValue: 3,
            min: 2,
            max: 20,
            step: 1
          },
          {
            key: 'cvBandwidthGrid',
            label: 'Bandwidths candidatos',
            type: 'number',
            help:
              'Cantidad de valores candidatos evaluados por kernel.',
            defaultValue: 25,
            min: 3,
            step: 1
          },
          {
            key: 'minBandwidth',
            label: 'Bandwidth mínimo',
            type: 'number',
            help:
              'Límite inferior de suavizado para evitar curvas artificialmente estrechas.',
            defaultValue: 0.001,
            min: 0.000001,
            step: 0.001
          },
          {
            key: 'maxExpansions',
            label: 'Máximo de expansiones',
            type: 'number',
            help:
              'Cantidad de veces que se amplía la búsqueda si el mejor valor está en un borde.',
            defaultValue: 3,
            min: 0,
            step: 1
          },
          {
            key: 'kernelBandwidths',
            label: 'Bandwidth por kernel',
            type: 'text',
            help:
              'Permite fijar manualmente valores por kernel.',
            placeholder:
              'Ejemplo: gaussian=1.5, cauchy=2',
            defaultValue: '',
            fullWidth: true
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye el resumen de kernels y bandwidths evaluados.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     KRUSKAL-WALLIS
  ======================================================= */

  kruskal: {
    analysisKey: 'kruskal',

    title: 'Configurar Kruskal-Wallis',
    description:
      'Compara tres o más grupos independientes mediante una prueba no paramétrica.',

    actionLabel: 'Ejecutar Kruskal-Wallis',
    runningLabel: 'Comparando grupos…',

    recommendationTitle:
      'Comparación entre grupos',

    recommendationText:
      'Un resultado significativo indica que al menos un grupo difiere. Para identificar cuáles grupos presentan diferencias se requieren comparaciones post hoc.',

    sections: [
      {
        key: 'kruskal-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Grupos y variables',
        description:
          'Define las fuentes de grupos y valores que serán comparadas.',

        fields: [
          {
            key: 'groupsDataset',
            label: 'Dataset de grupos',
            type: 'dataset',
            help:
              'Dataset que contiene la columna utilizada para definir los grupos.',
            defaultValue: '',
            required: true
          },
          {
            key: 'valuesDataset',
            label: 'Dataset de valores',
            type: 'dataset',
            help:
              'Dataset que contiene las variables numéricas de respuesta.',
            defaultValue: '',
            required: true
          },
          {
            key: 'groupColumn',
            label: 'Columna de grupo',
            type: 'column',
            help:
              'Variable categórica que define los grupos comparados.',
            defaultValue: '',
            datasetKey: 'groupsDataset',
            required: true
          },
          {
            key: 'groupId',
            label: 'ID del dataset de grupos',
            type: 'column',
            help:
              'Columna que identifica de forma única cada observación.',
            defaultValue: '',
            datasetKey: 'groupsDataset'
          },
          {
            key: 'valuesId',
            label: 'ID del dataset de valores',
            type: 'column',
            help:
              'Columna utilizada para vincular los valores con los grupos.',
            defaultValue: '',
            datasetKey: 'valuesDataset'
          },
          {
            key: 'variables',
            label: 'Variables de respuesta',
            type: 'variables',
            help:
              'Variables numéricas que serán comparadas entre los grupos.',
            defaultValue: [],
            datasetKey: 'valuesDataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'alpha',
            label: 'Nivel de significancia',
            type: 'number',
            help:
              'Umbral utilizado para evaluar diferencias estadísticas.',
            defaultValue: 0.05,
            min: 0.001,
            max: 1,
            step: 0.001
          },
          {
            key: 'minGroupSize',
            label: 'Mínimo por grupo',
            type: 'number',
            help:
              'Cantidad mínima de observaciones válidas exigida en cada grupo.',
            defaultValue: 3,
            min: 2,
            step: 1
          },
          {
            key: 'applyFdr',
            label: 'Aplicar corrección FDR',
            type: 'boolean',
            help:
              'Controla los falsos descubrimientos cuando se prueban varias variables.',
            defaultValue: true
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Agrega un resumen general de las pruebas.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     MANN-WHITNEY
  ======================================================= */

  mann: {
    analysisKey: 'mann',

    title: 'Configurar Mann-Whitney',
    description:
      'Compara la distribución de una o varias variables entre dos grupos independientes.',

    actionLabel: 'Ejecutar Mann-Whitney',
    runningLabel: 'Comparando dos grupos…',

    recommendationTitle:
      'Selección de grupos',

    recommendationText:
      'Selecciona exactamente dos categorías. La alternativa bilateral evalúa cualquier diferencia; las alternativas unilaterales requieren una hipótesis direccional previa.',

    sections: [
      {
        key: 'mann-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Grupos y variables',
        description:
          'Configura los dos grupos y las variables que deseas comparar.',

        fields: [
          {
            key: 'groupsDataset',
            label: 'Dataset de grupos',
            type: 'dataset',
            help:
              'Dataset que contiene la variable categórica de agrupación.',
            defaultValue: '',
            required: true
          },
          {
            key: 'valuesDataset',
            label: 'Dataset de valores',
            type: 'dataset',
            help:
              'Dataset que contiene las variables de respuesta.',
            defaultValue: '',
            required: true
          },
          {
            key: 'groupColumn',
            label: 'Columna de grupo',
            type: 'column',
            help:
              'Variable categórica de la que se seleccionarán dos grupos.',
            defaultValue: '',
            datasetKey: 'groupsDataset',
            required: true
          },
          {
            key: 'groupsToCompare',
            label: 'Grupos a comparar',
            type: 'group-values',
            help:
              'Selecciona exactamente dos valores de la columna de grupo.',
            defaultValue: [],
            datasetKey: 'groupsDataset',
            columnKey: 'groupColumn',
            multiple: true,
            required: true
          },
          {
            key: 'groupId',
            label: 'ID del dataset de grupos',
            type: 'column',
            help:
              'Identificador utilizado para vincular los grupos con los valores.',
            defaultValue: '',
            datasetKey: 'groupsDataset'
          },
          {
            key: 'valuesId',
            label: 'ID del dataset de valores',
            type: 'column',
            help:
              'Identificador correspondiente en el dataset de valores.',
            defaultValue: '',
            datasetKey: 'valuesDataset'
          },
          {
            key: 'variables',
            label: 'Variables de respuesta',
            type: 'variables',
            help:
              'Variables numéricas que se compararán entre los dos grupos.',
            defaultValue: [],
            datasetKey: 'valuesDataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'alternative',
            label: 'Hipótesis alternativa',
            type: 'select',
            help:
              'Define si se evalúa una diferencia bilateral o direccional.',
            defaultValue: 'two-sided',
            options: [
              {
                value: 'two-sided',
                label: 'Bilateral'
              },
              {
                value: 'less',
                label: 'Primer grupo menor'
              },
              {
                value: 'greater',
                label: 'Primer grupo mayor'
              }
            ]
          },
          {
            key: 'alpha',
            label: 'Nivel de significancia',
            type: 'number',
            help:
              'Umbral utilizado para interpretar la prueba.',
            defaultValue: 0.05,
            min: 0.001,
            max: 1,
            step: 0.001
          },
          {
            key: 'minGroupSize',
            label: 'Mínimo por grupo',
            type: 'number',
            help:
              'Número mínimo de observaciones válidas requerido en cada grupo.',
            defaultValue: 3,
            min: 2,
            step: 1
          },
          {
            key: 'applyFdr',
            label: 'Aplicar corrección FDR',
            type: 'boolean',
            help:
              'Controla falsos descubrimientos al comparar varias variables.',
            defaultValue: true
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye un resumen de las comparaciones realizadas.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     REDUCCIÓN DIMENSIONAL
  ======================================================= */

  reduction: {
    analysisKey: 'reduction',

    title: 'Configurar reducción dimensional',
    description:
      'Preprocesa las variables y construye una representación de menor dimensión.',

    actionLabel: 'Ejecutar reducción',
    runningLabel: 'Reduciendo dimensiones…',

    recommendationTitle:
      'Interpretación del embedding',

    recommendationText:
      'PCA es la opción inicial más interpretable. Los métodos no lineales pueden revelar estructuras locales, pero sus distancias globales deben interpretarse con cautela.',

    sections: [
      {
        key: 'reduction-data',
        eyebrow: 'DATOS',
        title: 'Datos y preprocesamiento',
        description:
          'Selecciona las variables y define cómo se tratarán faltantes y valores de abundancia.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset principal',
            type: 'dataset',
            help:
              'Dataset que contiene las variables del análisis.',
            defaultValue: '',
            required: true
          },
          {
            key: 'idColumn',
            label: 'Columna ID',
            type: 'column',
            help:
              'Identificador que no debe ser utilizado como feature.',
            defaultValue: '',
            datasetKey: 'dataset'
          },
          {
            key: 'features',
            label: 'Features',
            type: 'variables',
            help:
              'Variables numéricas que entrarán al modelo.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'missingStrategy',
            label: 'Tratamiento de faltantes',
            type: 'select',
            help:
              'Método empleado para manejar valores ausentes.',
            defaultValue: 'fill_zero',
            options: [
              {
                value: 'fill_zero',
                label: 'Completar con cero'
              },
              {
                value: 'drop_rows',
                label: 'Eliminar filas'
              },
              {
                value: 'median',
                label: 'Completar con mediana'
              }
            ]
          },
          {
            key: 'removeZeroRows',
            label: 'Quitar filas con suma cero',
            type: 'boolean',
            help:
              'Elimina observaciones sin abundancia en todas las variables.',
            defaultValue: true
          },
          {
            key: 'minPrevalence',
            label: 'Prevalencia mínima',
            type: 'number',
            help:
              'Proporción mínima de observaciones positivas para conservar una feature.',
            defaultValue: 0,
            min: 0,
            max: 1,
            step: 0.01
          },
          {
            key: 'minAbundance',
            label: 'Abundancia total mínima',
            type: 'number',
            help:
              'Suma mínima requerida para conservar una feature.',
            defaultValue: 0,
            min: 0,
            step: 0.1
          }
        ]
      },
      {
        key: 'reduction-model',
        eyebrow: 'MODELO',
        title: 'Reducción dimensional',
        description:
          'Configura la transformación, escalado y método de embedding.',

        fields: [
          {
            key: 'transformMethod',
            label: 'Transformación',
            type: 'select',
            help:
              'Transformación aplicada antes de calcular el embedding.',
            defaultValue: 'none',
            options: [
              {
                value: 'none',
                label: 'Sin transformación'
              },
              {
                value: 'log1p',
                label: 'Log1p'
              },
              {
                value: 'clr',
                label: 'CLR'
              }
            ]
          },
          {
            key: 'pseudocount',
            label: 'Pseudocount',
            type: 'number',
            help:
              'Valor agregado para evitar logaritmos de cero.',
            defaultValue: 1,
            min: 0.000001,
            step: 0.1
          },
          {
            key: 'scale',
            label: 'Escalar variables',
            type: 'boolean',
            help:
              'Estandariza las variables para evitar que una escala domine el análisis.',
            defaultValue: true
          },
          {
            key: 'embeddingMethod',
            label: 'Método de embedding',
            type: 'select',
            help:
              'Técnica utilizada para construir la representación reducida.',
            defaultValue: 'pca',
            options: [
              {
                value: 'pca',
                label: 'PCA'
              },
              {
                value: 'tsne',
                label: 't-SNE'
              },
              {
                value: 'umap',
                label: 'UMAP'
              }
            ]
          },
          {
            key: 'components',
            label: 'Número de componentes',
            type: 'number',
            help:
              'Dimensiones generadas por el método de reducción.',
            defaultValue: 3,
            min: 2,
            step: 1
          },
          {
            key: 'randomState',
            label: 'Semilla aleatoria',
            type: 'number',
            help:
              'Permite reproducir resultados en métodos estocásticos.',
            defaultValue: 42,
            step: 1
          },
          {
            key: 'embeddingJson',
            label: 'Parámetros avanzados',
            type: 'textarea',
            help:
              'Opciones adicionales del método en formato JSON.',
            placeholder:
              '{"perplexity": 20}',
            defaultValue: '',
            fullWidth: true
          },
          {
            key: 'pcaThresholds',
            label: 'Umbrales de varianza PCA',
            type: 'text',
            help:
              'Umbrales para calcular cuántos componentes explican determinada proporción de varianza.',
            defaultValue: '0.8, 0.9, 0.95'
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye información sobre transformación y dimensiones generadas.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     DBSCAN
  ======================================================= */

  dbscan: {
    analysisKey: 'dbscan',

    title: 'Configurar DBSCAN',
    description:
      'Detecta agrupaciones basadas en densidad e identifica observaciones consideradas ruido.',

    actionLabel: 'Ejecutar DBSCAN',
    runningLabel: 'Calculando clusters…',

    recommendationTitle:
      'Selección de eps',

    recommendationText:
      'Utiliza la curva k-distance como guía inicial para eps y evalúa diferentes combinaciones con min_samples. El resultado debe validarse con métricas y conocimiento del dominio.',

    sections: [
      {
        key: 'dbscan-data',
        eyebrow: 'DATOS',
        title: 'Datos y limpieza',
        description:
          'Selecciona datasets, identificadores y filtros previos al clustering.',

        fields: [
          {
            key: 'dataDataset',
            label: 'Dataset de datos',
            type: 'dataset',
            help:
              'Dataset que contiene las features utilizadas para formar clusters.',
            defaultValue: '',
            required: true
          },
          {
            key: 'dataId',
            label: 'ID del dataset de datos',
            type: 'column',
            help:
              'Identificador único de las observaciones.',
            defaultValue: '',
            datasetKey: 'dataDataset'
          },
          {
            key: 'features',
            label: 'Features numéricas',
            type: 'variables',
            help:
              'Variables que entrarán al algoritmo DBSCAN.',
            defaultValue: [],
            datasetKey: 'dataDataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'metaDataset',
            label: 'Dataset de metadatos',
            type: 'dataset',
            help:
              'Dataset opcional utilizado para enriquecer el resultado.',
            defaultValue: ''
          },
          {
            key: 'metaId',
            label: 'ID del dataset meta',
            type: 'column',
            help:
              'Identificador empleado para unir los metadatos.',
            defaultValue: '',
            datasetKey: 'metaDataset'
          },
          {
            key: 'missingStrategy',
            label: 'Tratamiento de faltantes',
            type: 'select',
            help:
              'Método utilizado para manejar valores ausentes.',
            defaultValue: 'fill_zero',
            options: [
              {
                value: 'fill_zero',
                label: 'Completar con cero'
              },
              {
                value: 'drop_rows',
                label: 'Eliminar filas'
              },
              {
                value: 'median',
                label: 'Completar con mediana'
              }
            ]
          },
          {
            key: 'dropNonNumeric',
            label: 'Quitar variables no numéricas',
            type: 'boolean',
            help:
              'Excluye automáticamente columnas no numéricas.',
            defaultValue: true
          },
          {
            key: 'removeZeroRows',
            label: 'Quitar filas con suma cero',
            type: 'boolean',
            help:
              'Elimina observaciones sin valores positivos.',
            defaultValue: true
          },
          {
            key: 'minPrevalence',
            label: 'Prevalencia mínima',
            type: 'number',
            help:
              'Proporción mínima de observaciones positivas para conservar una variable.',
            defaultValue: 0,
            min: 0,
            max: 1,
            step: 0.01
          },
          {
            key: 'minAbundance',
            label: 'Abundancia total mínima',
            type: 'number',
            help:
              'Suma mínima exigida para conservar una variable.',
            defaultValue: 0,
            min: 0,
            step: 0.1
          }
        ]
      },
      {
        key: 'dbscan-model',
        eyebrow: 'MODELO',
        title: 'Parámetros de clustering',
        description:
          'Configura la densidad, transformación y representación utilizada por DBSCAN.',

        fields: [
          {
            key: 'eps',
            label: 'Radio eps',
            type: 'number',
            help:
              'Distancia máxima para considerar dos observaciones como vecinas.',
            defaultValue: 0.5,
            min: 0.000001,
            step: 0.01,
            required: true
          },
          {
            key: 'minSamples',
            label: 'Mínimo de vecinos',
            type: 'number',
            help:
              'Número mínimo de observaciones requerido para formar una región densa.',
            defaultValue: 5,
            min: 2,
            step: 1,
            required: true
          },
          {
            key: 'transformMethod',
            label: 'Transformación',
            type: 'select',
            help:
              'Transformación aplicada antes del clustering.',
            defaultValue: 'none',
            options: [
              {
                value: 'none',
                label: 'Sin transformación'
              },
              {
                value: 'log1p',
                label: 'Log1p'
              },
              {
                value: 'clr',
                label: 'CLR'
              }
            ]
          },
          {
            key: 'pseudocount',
            label: 'Pseudocount',
            type: 'number',
            help:
              'Valor agregado antes de aplicar CLR.',
            defaultValue: 1,
            min: 0.000001,
            step: 0.1
          },
          {
            key: 'scale',
            label: 'Escalar variables',
            type: 'boolean',
            help:
              'Estandariza las features antes de calcular distancias.',
            defaultValue: true
          },
          {
            key: 'embeddingMethod',
            label: 'Embedding previo',
            type: 'select',
            help:
              'Permite ejecutar DBSCAN sobre una representación reducida.',
            defaultValue: 'none',
            options: [
              {
                value: 'none',
                label: 'Sin reducción'
              },
              {
                value: 'pca',
                label: 'PCA'
              },
              {
                value: 'tsne',
                label: 't-SNE'
              },
              {
                value: 'umap',
                label: 'UMAP'
              }
            ]
          },
          {
            key: 'components',
            label: 'Número de componentes',
            type: 'number',
            help:
              'Dimensiones que conservará el embedding.',
            defaultValue: 3,
            min: 2,
            step: 1
          },
          {
            key: 'randomState',
            label: 'Semilla aleatoria',
            type: 'number',
            help:
              'Permite reproducir los resultados.',
            defaultValue: 42,
            step: 1
          },
          {
            key: 'embeddingJson',
            label: 'Parámetros avanzados',
            type: 'textarea',
            help:
              'Opciones adicionales del embedding en formato JSON.',
            placeholder:
              '{"perplexity": 20}',
            defaultValue: '',
            fullWidth: true
          }
        ]
      },
      {
        key: 'dbscan-output',
        eyebrow: 'RESULTADOS',
        title: 'Figuras y resumen',
        description:
          'Define los diagnósticos y resúmenes que acompañarán el clustering.',

        fields: [
          {
            key: 'calculateKDistance',
            label: 'Calcular curva k-distance',
            type: 'boolean',
            help:
              'Genera una curva para orientar la elección del parámetro eps.',
            defaultValue: true
          },
          {
            key: 'kDistanceMinSamples',
            label: 'Vecino para k-distance',
            type: 'number',
            help:
              'Vecino utilizado para construir la curva k-distance.',
            defaultValue: 5,
            min: 2,
            step: 1,
            visibleWhen: {
              field: 'calculateKDistance',
              equals: true
            }
          },
          {
            key: 'saveKDistanceFigure',
            label: 'Guardar figura k-distance',
            type: 'boolean',
            help:
              'Incluye la curva k-distance entre las figuras exportadas.',
            defaultValue: true,
            visibleWhen: {
              field: 'calculateKDistance',
              equals: true
            }
          },
          {
            key: 'saveEmbeddingFigure',
            label: 'Guardar figura del embedding',
            type: 'boolean',
            help:
              'Exporta la representación visual de los clusters.',
            defaultValue: true
          },
          {
            key: 'numericSummary',
            label: 'Variables de resumen numérico',
            type: 'variables',
            help:
              'Variables numéricas que serán resumidas por cluster.',
            defaultValue: [],
            datasetKey: 'dataDataset',
            multiple: true,
            allOption: false
          },
          {
            key: 'categoricalSummary',
            label: 'Variables de resumen categórico',
            type: 'variables',
            help:
              'Variables categóricas que serán contadas por cluster.',
            defaultValue: [],
            datasetKey: 'metaDataset',
            multiple: true,
            allOption: false
          },
          {
            key: 'aggregations',
            label: 'Agregaciones numéricas',
            type: 'text',
            help:
              'Operaciones utilizadas para resumir variables numéricas.',
            defaultValue: 'median',
            placeholder:
              'median, mean, min, max'
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye métricas, tamaños y cantidad de ruido.',
            defaultValue: true
          }
        ]
      }
    ]
  },


  /* =======================================================
     REVISIÓN DE CLUSTERS
  ======================================================= */

  review: {
    analysisKey: 'review',

    title: 'Configurar revisión de clusters',
    description:
      'Evalúa clusters existentes mediante tamaños, ruido y métricas internas.',

    actionLabel: 'Revisar clusterización',
    runningLabel: 'Revisando clusters…',

    recommendationTitle:
      'Validación de resultados',

    recommendationText:
      'Las métricas internas describen separación y compactación, pero no reemplazan la interpretación clínica o biológica de los grupos encontrados.',

    sections: [
      {
        key: 'review-parameters',
        eyebrow: 'CONFIGURACIÓN',
        title: 'Métricas y criterios',
        description:
          'Selecciona las features y la columna que contiene las etiquetas de cluster.',

        fields: [
          {
            key: 'dataset',
            label: 'Dataset principal',
            type: 'dataset',
            help:
              'Dataset que contiene features y etiquetas de cluster.',
            defaultValue: '',
            required: true
          },
          {
            key: 'clusterColumn',
            label: 'Columna de cluster',
            type: 'column',
            help:
              'Columna que contiene las etiquetas asignadas a cada observación.',
            defaultValue: '',
            datasetKey: 'dataset',
            required: true
          },
          {
            key: 'features',
            label: 'Features',
            type: 'variables',
            help:
              'Variables numéricas utilizadas para calcular métricas internas.',
            defaultValue: [],
            datasetKey: 'dataset',
            multiple: true,
            allOption: true
          },
          {
            key: 'ignoreNoise',
            label: 'Ignorar ruido',
            type: 'boolean',
            help:
              'Excluye las observaciones etiquetadas como ruido de las métricas internas.',
            defaultValue: true
          },
          {
            key: 'noiseLabel',
            label: 'Etiqueta de ruido',
            type: 'number',
            help:
              'Valor utilizado para identificar observaciones de ruido.',
            defaultValue: -1,
            step: 1
          },
          {
            key: 'minClusters',
            label: 'Mínimo de clusters',
            type: 'number',
            help:
              'Número mínimo de clusters válidos requerido para ejecutar las métricas.',
            defaultValue: 3,
            min: 2,
            step: 1
          },
          {
            key: 'showSummary',
            label: 'Mostrar resumen de ejecución',
            type: 'boolean',
            help:
              'Incluye tamaños, ruido, métricas y recomendación general.',
            defaultValue: true
          }
        ]
      }
    ]
  }
};