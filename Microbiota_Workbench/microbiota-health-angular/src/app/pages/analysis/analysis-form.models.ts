import { AnalysisKey } from '../../models/app.models';

/**
 * Tipos de controles que puede renderizar el formulario dinámico.
 */
export type AnalysisFieldType =
  | 'dataset'
  | 'column'
  | 'variables'
  | 'group-values'
  | 'select'
  | 'number'
  | 'text'
  | 'textarea'
  | 'boolean';

/**
 * Valor permitido dentro del formulario dinámico.
 */
export type AnalysisFieldValue =
  | string
  | number
  | boolean
  | string[]
  | null;

/**
 * Opción utilizada por controles desplegables.
 */
export interface AnalysisFieldOption {
  value: string | number | boolean;
  label: string;
  description?: string;
}

/**
 * Configuración de un campo individual.
 */
export interface AnalysisFieldConfig {
  /**
   * Identificador único dentro del formulario.
   */
  key: string;

  /**
   * Texto visible del campo.
   */
  label: string;

  /**
   * Tipo de control.
   */
  type: AnalysisFieldType;

  /**
   * Explicación mostrada en el tooltip.
   */
  help: string;

  /**
   * Texto secundario debajo del control.
   */
  description?: string;

  /**
   * Texto de ejemplo.
   */
  placeholder?: string;

  /**
   * Valor inicial.
   */
  defaultValue: AnalysisFieldValue;

  /**
   * Indica que el campo debe completarse.
   */
  required?: boolean;

  /**
   * Opciones para campos select.
   */
  options?: AnalysisFieldOption[];

  /**
   * Valor mínimo para números.
   */
  min?: number;

  /**
   * Valor máximo para números.
   */
  max?: number;

  /**
   * Incremento permitido para números.
   */
  step?: number;

  /**
   * Campo de dataset del cual se deben obtener las columnas.
   *
   * Ejemplo:
   * datasetKey: 'dataset'
   */
  datasetKey?: string;

  /**
   * Campo que contiene una columna categórica.
   * Se utiliza para cargar sus grupos disponibles.
   */
  columnKey?: string;

  /**
   * Permite seleccionar varias columnas.
   */
  multiple?: boolean;

  /**
   * Muestra la opción "Todas las variables".
   */
  allOption?: boolean;

  /**
   * Permite mostrar el campo ocupando toda la fila.
   */
  fullWidth?: boolean;

  /**
   * Cantidad de columnas visuales que ocupa.
   */
  columnSpan?: 1 | 2;

  /**
   * Campos que deben tener un valor para habilitar este control.
   */
  dependsOn?: string[];

  /**
   * Valor que debe tener otro campo para mostrar este control.
   */
  visibleWhen?: {
    field: string;
    equals: AnalysisFieldValue;
  };
}

/**
 * Agrupación visual de parámetros.
 */
export interface AnalysisFormSection {
  key: string;
  title: string;
  description?: string;
  eyebrow?: string;
  icon?: string;
  fields: AnalysisFieldConfig[];
}

/**
 * Información general del formulario de un análisis.
 */
export interface AnalysisFormConfig {
  analysisKey: AnalysisKey;

  title: string;
  description: string;

  actionLabel: string;
  runningLabel: string;

  recommendationTitle: string;
  recommendationText: string;

  sections: AnalysisFormSection[];

  /**
   * Permite mostrar una vista previa especial.
   * Se usará inicialmente en Visualizaciones.
   */
  previewType?: 'visual-builder';
}

/**
 * Estado del formulario dinámico.
 */
export type AnalysisFormValues = Record<
  string,
  AnalysisFieldValue
>;