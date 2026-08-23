import {
  Component,
  computed,
  inject,
  signal
} from '@angular/core';

import { FormsModule } from '@angular/forms';

import {
  ActivatedRoute,
  Router
} from '@angular/router';

import {
  AnalysisKey
} from '../../models/app.models';

import {
  WorkbenchStateService
} from '../../services/workbench-state.service';

import {
  ANALYSIS_FORMS
} from './analysis-form.config';

import {
  AnalysisFieldConfig,
  AnalysisFieldValue,
  AnalysisFormConfig,
  AnalysisFormValues
} from './analysis-form.models';


@Component({
  selector: 'app-analysis',
  standalone: true,
  imports: [
    FormsModule
  ],
  templateUrl: './analysis.component.html',
  styleUrl: './analysis.component.css'
})
export class AnalysisComponent {

  /* =======================================================
     SERVICIOS
  ======================================================= */

  readonly state = inject(WorkbenchStateService);

  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);


  /* =======================================================
     CONFIGURACIÓN GENERAL
  ======================================================= */

  readonly formConfigs = ANALYSIS_FORMS;

  /**
   * Estado independiente de cada formulario.
   *
   * Ejemplo:
   * {
   *   characterization: {
   *     dataset: 'microbiota_clinica_demo.csv',
   *     variables: [],
   *     mode: 'both'
   *   },
   *   normality: {
   *     ...
   *   }
   * }
   */
  readonly formsState = signal<
    Record<string, AnalysisFormValues>
  >({});


  /**
   * Campo múltiple que actualmente tiene abierto
   * su selector desplegable.
   */
  readonly openMultipleField = signal<string | null>(
    null
  );


  /* =======================================================
     EXPLORACIÓN
  ======================================================= */

  /**
   * Controla el desplegable especial de Exploración.
   */
  readonly variablesDropdownOpen = signal(false);


  /**
   * En Exploración:
   *
   * [] = todas las variables.
   */
  readonly selectedVariables = signal<string[]>([]);


  /* =======================================================
     COLUMNAS SIMULADAS DEL FRONTEND
  ======================================================= */

  /**
   * Por ahora las columnas están simuladas.
   *
   * Cuando conectemos la carga real de archivos,
   * este mapa será reemplazado por las columnas
   * detectadas en cada dataset.
   */
  private readonly datasetVariables: Record<
    string,
    string[]
  > = {
    'microbiota_clinica_demo.csv': [
      'ID',
      'Ciudad',
      'Sexo',
      'Edad',
      'Grupo_etario',
      'HDL',
      'LDL',
      'Colesterol',
      'Trigliceridos',
      'hsCRP',
      'Glucosa',
      'Hemoglobina_glicosilada',
      'Adiponectina',
      'Insulina',
      'HOMA_IR',
      'Presion_sistolica',
      'Presion_diastolica',
      'IMC',
      'Clase_IMC',
      'Grasa_corporal',
      'Cintura',
      'Medicamento',
      'Fibra',
      'Proteina_total',
      'Proteina_animal',
      'Indice_diversidad',
      'Diagnostico',
      'Cluster',
      'DBSCAN_cluster'
    ],

    'metadatos_pacientes.csv': [
      'ID',
      'Ciudad',
      'Sexo',
      'Edad',
      'Grupo_etario',
      'Diagnostico',
      'Medicamento',
      'Dieta',
      'Actividad_fisica',
      'Peso',
      'Talla',
      'IMC',
      'Presion_sistolica',
      'Presion_diastolica'
    ]
  };


  /**
   * Valores categóricos simulados.
   *
   * Se utilizan en controles como:
   * "Grupos a comparar".
   */
  private readonly datasetGroupValues: Record<
    string,
    Record<string, string[]>
  > = {
    'microbiota_clinica_demo.csv': {
      Sexo: [
        'Femenino',
        'Masculino'
      ],

      Diagnostico: [
        'Control',
        'Riesgo',
        'Diagnóstico'
      ],

      Grupo_etario: [
        'Adulto joven',
        'Adulto',
        'Adulto mayor'
      ],

      Ciudad: [
        'Bogotá',
        'Medellín',
        'Cali',
        'Barranquilla'
      ],

      Clase_IMC: [
        'Normal',
        'Sobrepeso',
        'Obesidad'
      ]
    },

    'metadatos_pacientes.csv': {
      Sexo: [
        'Femenino',
        'Masculino'
      ],

      Diagnostico: [
        'Control',
        'Riesgo',
        'Diagnóstico'
      ],

      Grupo_etario: [
        'Adulto joven',
        'Adulto',
        'Adulto mayor'
      ],

      Dieta: [
        'Omnívora',
        'Vegetariana',
        'Mediterránea'
      ],

      Actividad_fisica: [
        'Baja',
        'Moderada',
        'Alta'
      ]
    }
  };


  /* =======================================================
     VALORES CALCULADOS
  ======================================================= */

  /**
   * Configuración del análisis dinámico seleccionado.
   *
   * Exploración no está incluida porque conserva
   * su interfaz especializada.
   */
  readonly currentForm = computed<
    AnalysisFormConfig | null
  >(() => {
    const analysisKey =
      this.state.selectedAnalysis();

    return (
      this.formConfigs[analysisKey] ??
      null
    );
  });


  /**
   * Estado actual del formulario seleccionado.
   */
  readonly currentFormValues = computed<
    AnalysisFormValues
  >(() => {
    const analysisKey =
      this.state.selectedAnalysis();

    return (
      this.formsState()[analysisKey] ??
      {}
    );
  });


  /**
   * Variables disponibles para Exploración.
   */
  readonly availableVariables = computed<
    string[]
  >(() => {
    const datasetName =
      this.state.selectedDataset();

    return this.state.getColumns(datasetName);
  });


  /**
   * En Exploración, lista vacía significa
   * "Todas las variables".
   */
  readonly allVariablesSelected = computed(
    () =>
      this.selectedVariables().length === 0
  );


  /**
   * Texto principal del selector de Exploración.
   */
  readonly variablesDropdownLabel = computed(
    () => {
      const variables =
        this.selectedVariables();

      if (variables.length === 0) {
        return 'Todas las variables';
      }

      if (variables.length === 1) {
        return variables[0];
      }

      if (variables.length === 2) {
        return variables.join(', ');
      }

      return `${variables.length} variables seleccionadas`;
    }
  );


  /**
   * Texto secundario del selector de Exploración.
   */
  readonly variablesDescription = computed(
    () => {
      const selectedCount =
        this.selectedVariables().length;

      const total =
        this.availableVariables().length;

      if (selectedCount === 0) {
        return `Se incluirán las ${total} variables disponibles.`;
      }

      return `${selectedCount} de ${total} variables seleccionadas.`;
    }
  );


  /* =======================================================
     CONSTRUCTOR
  ======================================================= */

  constructor() {
    this.initializeForms();

    this.route.paramMap.subscribe(
      (params) => {
        const key = params.get(
          'analysisKey'
        ) as AnalysisKey | null;

        if (
          key &&
          this.state.analyses.some(
            (analysis) =>
              analysis.key === key
          )
        ) {
          this.state.selectAnalysis(key);
          this.ensureFormInitialized(key);
        }
      }
    );
  }


  /* =======================================================
     INICIALIZACIÓN DE FORMULARIOS
  ======================================================= */

  /**
   * Construye el estado inicial de todos los análisis.
   */
  private initializeForms(): void {
    const initialState: Record<
      string,
      AnalysisFormValues
    > = {};

    for (
      const [analysisKey, config]
      of Object.entries(this.formConfigs)
    ) {
      initialState[analysisKey] =
        this.createInitialValues(config);
    }

    this.formsState.set(initialState);
  }


  /**
   * Genera los valores iniciales de un formulario.
   */
  private createInitialValues(
    config: AnalysisFormConfig
  ): AnalysisFormValues {
    const values: AnalysisFormValues = {};

    for (const section of config.sections) {
      for (const field of section.fields) {
        let initialValue =
          this.cloneValue(
            field.defaultValue
          );

        /*
         * Los campos de tipo dataset se inicializan
         * con el dataset seleccionado globalmente.
         */
        if (
          field.type === 'dataset' &&
          (
            initialValue === '' ||
            initialValue === null
          )
        ) {
          initialValue =
            this.state.selectedDataset();
        }

        values[field.key] =
          initialValue;
      }
    }

    return values;
  }


  /**
   * Garantiza que un análisis tenga estado creado.
   */
  private ensureFormInitialized(
    analysisKey: AnalysisKey
  ): void {
    if (analysisKey === 'exploration') {
      return;
    }

    const existing =
      this.formsState()[analysisKey];

    if (existing) {
      return;
    }

    const config =
      this.formConfigs[analysisKey];

    if (!config) {
      return;
    }

    this.formsState.update(
      (forms) => ({
        ...forms,

        [analysisKey]:
          this.createInitialValues(config)
      })
    );
  }


  /**
   * Clona arreglos para evitar compartir referencias
   * entre formularios.
   */
  private cloneValue(
    value: AnalysisFieldValue
  ): AnalysisFieldValue {
    if (Array.isArray(value)) {
      return [...value];
    }

    return value;
  }


  /* =======================================================
     NAVEGACIÓN
  ======================================================= */

  /**
   * Cambia de análisis desde el catálogo lateral.
   */
  select(key: AnalysisKey): void {
    this.closeAllDropdowns();

    this.state.selectAnalysis(key);
    this.ensureFormInitialized(key);

    void this.router.navigate([
      '/analisis',
      key
    ]);
  }


  /**
   * Abre la página del asistente.
   */
  goToAssistant(): void {
    this.closeAllDropdowns();

    void this.router.navigate([
      '/asistente'
    ]);
  }


  /* =======================================================
     EXPLORACIÓN
  ======================================================= */

  /**
   * Cambia el dataset de Exploración.
   */
  changeDataset(
    datasetName: string
  ): void {
    this.state.selectedDataset.set(
      datasetName
    );

    this.selectedVariables.set([]);
    this.variablesDropdownOpen.set(false);
  }


  /**
   * Abre o cierra el selector de Exploración.
   */
  toggleVariablesDropdown(): void {
    this.openMultipleField.set(null);

    this.variablesDropdownOpen.update(
      (isOpen) => !isOpen
    );
  }


  /**
   * Selecciona todas las variables
   * en Exploración.
   */
  selectAllVariables(): void {
    this.selectedVariables.set([]);
    this.variablesDropdownOpen.set(false);
  }


  /**
   * Selecciona o elimina una variable
   * en Exploración.
   */
  toggleVariable(
    variable: string
  ): void {
    const current =
      this.selectedVariables();

    if (current.includes(variable)) {
      this.selectedVariables.set(
        current.filter(
          (item) =>
            item !== variable
        )
      );

      return;
    }

    this.selectedVariables.set([
      ...current,
      variable
    ]);
  }


  /**
   * Revisa si una variable está seleccionada
   * en Exploración.
   */
  isVariableSelected(
    variable: string
  ): boolean {
    return this.selectedVariables()
      .includes(variable);
  }


  /**
   * Restablece Exploración a todas las variables.
   */
  resetVariables(): void {
    this.selectAllVariables();
  }


  /* =======================================================
     FORMULARIOS DINÁMICOS
  ======================================================= */

  /**
   * Obtiene el valor actual de un campo.
   */
  getFieldValue(
    fieldKey: string
  ): AnalysisFieldValue {
    return (
      this.currentFormValues()[fieldKey] ??
      null
    );
  }


  /**
   * Obtiene un valor como texto.
   */
  getStringValue(
    fieldKey: string
  ): string {
    const value =
      this.getFieldValue(fieldKey);

    return typeof value === 'string'
      ? value
      : '';
  }


  /**
   * Obtiene un valor numérico.
   */
  getNumberValue(
    fieldKey: string
  ): number | null {
    const value =
      this.getFieldValue(fieldKey);

    return typeof value === 'number'
      ? value
      : null;
  }


  /**
   * Obtiene un valor booleano.
   */
  getBooleanValue(
    fieldKey: string
  ): boolean {
    return (
      this.getFieldValue(fieldKey) === true
    );
  }


  /**
   * Obtiene un valor múltiple.
   */
  getArrayValue(
    fieldKey: string
  ): string[] {
    const value =
      this.getFieldValue(fieldKey);

    return Array.isArray(value)
      ? value
      : [];
  }


  /**
   * Actualiza un campo del análisis seleccionado.
   */
  updateField(
    fieldKey: string,
    value: AnalysisFieldValue
  ): void {
    const analysisKey =
      this.state.selectedAnalysis();

    if (analysisKey === 'exploration') {
      return;
    }

    const config =
      this.currentForm();

    if (!config) {
      return;
    }

    this.formsState.update(
      (forms) => {
        const currentValues =
          forms[analysisKey] ?? {};

        const updatedValues: AnalysisFormValues =
          {
            ...currentValues,
            [fieldKey]:
              this.cloneValue(value)
          };

        /*
         * Si cambia un dataset, limpiamos los campos
         * que dependen de él.
         */
        for (
          const section
          of config.sections
        ) {
          for (
            const field
            of section.fields
          ) {
            if (
              field.datasetKey === fieldKey
            ) {
              if (
                field.type === 'variables' ||
                field.type === 'group-values'
              ) {
                updatedValues[field.key] = [];
              } else {
                updatedValues[field.key] = '';
              }
            }

            /*
             * Si cambia una columna usada para obtener
             * categorías, limpiamos los grupos.
             */
            if (
              field.columnKey === fieldKey
            ) {
              updatedValues[field.key] = [];
            }
          }
        }

        return {
          ...forms,
          [analysisKey]:
            updatedValues
        };
      }
    );

    /*
     * Si el campo principal se llama dataset,
     * actualizamos el contexto global.
     */
    if (
      fieldKey === 'dataset' &&
      typeof value === 'string'
    ) {
      this.state.selectedDataset.set(value);
    }
  }


  /**
   * Maneja inputs de texto.
   */
  updateTextField(
    fieldKey: string,
    value: string
  ): void {
    this.updateField(
      fieldKey,
      value
    );
  }


  /**
   * Maneja inputs numéricos.
   */
  updateNumberField(
    fieldKey: string,
    value: string | number | null
  ): void {
    if (
      value === '' ||
      value === null
    ) {
      this.updateField(
        fieldKey,
        null
      );

      return;
    }

    const parsedValue =
      Number(value);

    this.updateField(
      fieldKey,
      Number.isFinite(parsedValue)
        ? parsedValue
        : null
    );
  }


  /**
   * Maneja controles booleanos.
   */
  updateBooleanField(
    fieldKey: string,
    value: boolean
  ): void {
    this.updateField(
      fieldKey,
      value
    );
  }


  /* =======================================================
     VISIBILIDAD CONDICIONAL
  ======================================================= */

  /**
   * Determina si un campo debe mostrarse.
   */
  isFieldVisible(
    field: AnalysisFieldConfig
  ): boolean {
    if (!field.visibleWhen) {
      return true;
    }

    const currentValue =
      this.getFieldValue(
        field.visibleWhen.field
      );

    return this.valuesAreEqual(
      currentValue,
      field.visibleWhen.equals
    );
  }


  /**
   * Comprueba condiciones de visibilidad.
   */
  private valuesAreEqual(
    first: AnalysisFieldValue,
    second: AnalysisFieldValue
  ): boolean {
    if (
      Array.isArray(first) &&
      Array.isArray(second)
    ) {
      return (
        JSON.stringify(first) ===
        JSON.stringify(second)
      );
    }

    return first === second;
  }


  /* =======================================================
     COLUMNAS Y GRUPOS
  ======================================================= */

  /**
   * Obtiene las columnas disponibles para un campo.
   */
  getColumnsForField(
    field: AnalysisFieldConfig
  ): string[] {
    const datasetName =
      this.getDatasetNameForField(field);

    return this.state.getColumns(datasetName);
  }


  /**
   * Obtiene el dataset asociado a un campo.
   */
  private getDatasetNameForField(
    field: AnalysisFieldConfig
  ): string {
    if (field.datasetKey) {
      const datasetValue =
        this.getFieldValue(
          field.datasetKey
        );

      if (typeof datasetValue === 'string') {
        return datasetValue;
      }
    }

    return this.state.selectedDataset();
  }


  /**
   * Obtiene los grupos categóricos disponibles.
   */
  getGroupValuesForField(
    field: AnalysisFieldConfig
  ): string[] {
    const datasetName =
      this.getDatasetNameForField(field);

    if (!field.columnKey) {
      return [];
    }

    const columnValue =
      this.getFieldValue(
        field.columnKey
      );

    if (typeof columnValue !== 'string') {
      return [];
    }

    return this.state.getCategories(datasetName, columnValue);
  }


  /* =======================================================
     SELECTORES MÚLTIPLES DINÁMICOS
  ======================================================= */

  /**
   * Abre o cierra un selector múltiple.
   */
  toggleMultipleDropdown(
    fieldKey: string
  ): void {
    this.variablesDropdownOpen.set(false);

    this.openMultipleField.update(
      (current) =>
        current === fieldKey
          ? null
          : fieldKey
    );
  }


  /**
   * Indica si un selector está abierto.
   */
  isMultipleDropdownOpen(
    fieldKey: string
  ): boolean {
    return (
      this.openMultipleField() ===
      fieldKey
    );
  }


  /**
   * Selecciona o elimina un valor múltiple.
   */
  toggleMultipleValue(
    field: AnalysisFieldConfig,
    value: string
  ): void {
    const current =
      this.getArrayValue(field.key);

    if (current.includes(value)) {
      this.updateField(
        field.key,
        current.filter(
          (item) =>
            item !== value
        )
      );

      return;
    }

    /*
     * Mann-Whitney solo admite dos grupos.
     */
    if (
      field.type === 'group-values' &&
      current.length >= 2
    ) {
      this.updateField(
        field.key,
        [
          current[1],
          value
        ]
      );

      return;
    }

    this.updateField(
      field.key,
      [
        ...current,
        value
      ]
    );
  }


  /**
   * Selecciona la opción "Todas".
   *
   * [] representa todas las variables cuando
   * allOption está habilitado.
   */
  selectAllField(
    field: AnalysisFieldConfig
  ): void {
    this.updateField(
      field.key,
      []
    );

    this.openMultipleField.set(null);
  }


  /**
   * Revisa si un valor está seleccionado.
   */
  isMultipleValueSelected(
    fieldKey: string,
    value: string
  ): boolean {
    return this.getArrayValue(fieldKey)
      .includes(value);
  }


  /**
   * Indica si está activa la opción "Todas".
   */
  isAllOptionSelected(
    field: AnalysisFieldConfig
  ): boolean {
    return (
      field.allOption === true &&
      this.getArrayValue(field.key)
        .length === 0
    );
  }


  /**
   * Opciones visibles de un campo múltiple.
   */
  getMultipleOptions(
    field: AnalysisFieldConfig
  ): string[] {
    if (field.type === 'group-values') {
      return this.getGroupValuesForField(
        field
      );
    }

    return this.getColumnsForField(field);
  }


  /**
   * Texto principal de un selector múltiple.
   */
  getMultipleFieldLabel(
    field: AnalysisFieldConfig
  ): string {
    const selected =
      this.getArrayValue(field.key);

    if (
      field.allOption &&
      selected.length === 0
    ) {
      return 'Todas las variables';
    }

    if (selected.length === 0) {
      return 'Seleccionar opciones';
    }

    if (selected.length === 1) {
      return selected[0];
    }

    if (selected.length === 2) {
      return selected.join(', ');
    }

    return `${selected.length} seleccionadas`;
  }


  /**
   * Texto secundario de un selector múltiple.
   */
  getMultipleFieldDescription(
    field: AnalysisFieldConfig
  ): string {
    const options =
      this.getMultipleOptions(field);

    const selected =
      this.getArrayValue(field.key);

    if (
      field.allOption &&
      selected.length === 0
    ) {
      return `Se incluirán las ${options.length} variables disponibles.`;
    }

    if (selected.length === 0) {
      if (field.type === 'group-values') {
        return 'Selecciona exactamente dos grupos.';
      }

      return `${options.length} opciones disponibles.`;
    }

    if (field.type === 'group-values') {
      return `${selected.length} de 2 grupos seleccionados.`;
    }

    return `${selected.length} de ${options.length} seleccionadas.`;
  }


  /**
   * Elimina todos los valores de un selector.
   */
  clearMultipleField(
    field: AnalysisFieldConfig
  ): void {
    this.updateField(
      field.key,
      []
    );
  }


  /* =======================================================
     VALIDACIÓN
  ======================================================= */

  /**
   * Determina si el formulario actual puede ejecutarse.
   */
  readonly canRunCurrentAnalysis =
    computed(() => {
      if (
        this.state.selectedAnalysis() ===
        'exploration'
      ) {
        return true;
      }

      const config =
        this.currentForm();

      if (!config) {
        return false;
      }

      const values =
        this.currentFormValues();

      for (
        const section
        of config.sections
      ) {
        for (
          const field
          of section.fields
        ) {
          if (
            !field.required ||
            !this.isFieldVisible(field)
          ) {
            continue;
          }

          const value =
            values[field.key];

          if (
            value === null ||
            value === undefined ||
            value === ''
          ) {
            return false;
          }

          if (
            Array.isArray(value) &&
            value.length === 0 &&
            !field.allOption
          ) {
            return false;
          }
        }
      }

      return true;
    });


  /* =======================================================
     EJECUCIÓN
  ======================================================= */

  /**
   * Ejecuta Exploración o cualquier formulario dinámico.
   */
  async run(): Promise<void> {
    if (this.state.analysisRunning()) {
      return;
    }

    const analysisKey = this.state.selectedAnalysis();
    let params: Record<string, unknown>;

    if (analysisKey === 'exploration') {
      if (!this.state.selectedDataset()) {
        this.state.showToast('Carga y selecciona un dataset antes de ejecutar.');
        return;
      }
      params = {
        dataset: this.state.selectedDataset(),
        variables: this.selectedVariables(),
        maxCategoryValues: 12,
        showSummary: true
      };
    } else {
      if (!this.canRunCurrentAnalysis()) {
        this.state.showToast('Completa los parámetros obligatorios antes de ejecutar.');
        return;
      }
      params = { ...this.currentFormValues() };
    }

    this.closeAllDropdowns();
    const ok = await this.state.runAnalysis(params);
    if (ok) {
      void this.router.navigate(['/resultados']);
    }
  }


  /**
   * Etiqueta del botón de ejecución.
   */
  getActionLabel(): string {
    if (
      this.state.selectedAnalysis() ===
      'exploration'
    ) {
      return 'Ejecutar exploración';
    }

    return (
      this.currentForm()?.actionLabel ??
      'Ejecutar análisis'
    );
  }


  /**
   * Etiqueta mientras el análisis está ejecutándose.
   */
  getRunningLabel(): string {
    if (
      this.state.selectedAnalysis() ===
      'exploration'
    ) {
      return 'Ejecutando exploración…';
    }

    return (
      this.currentForm()?.runningLabel ??
      'Ejecutando análisis…'
    );
  }


  /* =======================================================
     RESTABLECER
  ======================================================= */

  /**
   * Restablece el formulario seleccionado.
   */
  resetCurrentForm(): void {
    const analysisKey =
      this.state.selectedAnalysis();

    this.closeAllDropdowns();

    if (analysisKey === 'exploration') {
      this.selectedVariables.set([]);

      return;
    }

    const config =
      this.currentForm();

    if (!config) {
      return;
    }

    this.formsState.update(
      (forms) => ({
        ...forms,

        [analysisKey]:
          this.createInitialValues(config)
      })
    );
  }


  /* =======================================================
     UTILIDADES
  ======================================================= */

  /**
   * Cierra todos los selectores abiertos.
   */
  closeAllDropdowns(): void {
    this.variablesDropdownOpen.set(false);
    this.openMultipleField.set(null);
  }


  /**
   * Obtiene el dataset activo de un formulario.
   */
  getCurrentDatasetName(): string {
    const analysisKey =
      this.state.selectedAnalysis();

    if (analysisKey === 'exploration') {
      return this.state.selectedDataset();
    }

    const values =
      this.currentFormValues();

    const candidateKeys = [
      'dataset',
      'dataDataset',
      'groupsDataset',
      'valuesDataset'
    ];

    for (const key of candidateKeys) {
      const value = values[key];

      if (
        typeof value === 'string' &&
        value
      ) {
        return value;
      }
    }

    return this.state.selectedDataset();
  }


  /**
   * Texto inferior de la configuración actual.
   */
  getCurrentSelectionSummary(): string {
    const analysisKey =
      this.state.selectedAnalysis();

    if (analysisKey === 'exploration') {
      return this.selectedVariables()
        .length === 0
        ? 'Todas las variables'
        : `${this.selectedVariables().length} variables seleccionadas`;
    }

    const values =
      this.currentFormValues();

    const multipleKeys = [
      'variables',
      'features',
      'numericSummary',
      'violinVariables',
      'abundanceColumns'
    ];

    for (const key of multipleKeys) {
      const value = values[key];

      if (Array.isArray(value)) {
        return value.length === 0
          ? 'Todas las variables disponibles'
          : `${value.length} variables seleccionadas`;
      }
    }

    return 'Parámetros configurados';
  }
}