import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { AnalysisItem, AnalysisKey, AnalysisRun, DatasetItem } from '../models/app.models';

@Injectable({ providedIn: 'root' })
export class WorkbenchStateService {
  private readonly http = inject(HttpClient);
  readonly sidebarCollapsed = signal(false);
  readonly selectedAnalysis = signal<AnalysisKey>('exploration');
  readonly selectedDataset = signal('');
  readonly analysisRunning = signal(false);
  readonly loadingDatasets = signal(false);
  readonly toast = signal('');
  readonly question = signal('Quiero comparar glucosa entre grupos de sexo. ¿Qué prueba y parámetros debo usar?');
  readonly assistantMessage = signal('Carga un dataset y cuéntame qué quieres investigar. Te ayudaré a elegir la prueba, preparar los datos e interpretar el resultado.');
  readonly assistantLoading = signal(false);
  readonly datasets = signal<DatasetItem[]>([]);
  readonly runs = signal<AnalysisRun[]>([]);
  readonly currentRun = signal<AnalysisRun | null>(null);

  readonly analyses: AnalysisItem[] = [
    { key: 'exploration', name: 'Exploración', description: 'Perfilado, faltantes y calidad de variables.', category: 'Preparación', icon: '⌕' },
    { key: 'characterization', name: 'Caracterización', description: 'Resúmenes descriptivos e histogramas.', category: 'Descriptivo', icon: '▥' },
    { key: 'normality', name: 'Normalidad', description: 'Shapiro, Anderson y revisión de supuestos.', category: 'Estadística', icon: '∿' },
    { key: 'correlation', name: 'Correlación', description: 'Pearson, Spearman y mapas de calor.', category: 'Estadística', icon: '⌁' },
    { key: 'visualization', name: 'Visualizaciones', description: 'Gráficas clínicas, abundancia y constructor.', category: 'Visual', icon: '◫' },
    { key: 'kde', name: 'KDE', description: 'Estimación de densidad y comparación de kernels.', category: 'Distribución', icon: '≋' },
    { key: 'kruskal', name: 'Kruskal-Wallis', description: 'Comparación no paramétrica de tres o más grupos.', category: 'Pruebas', icon: 'K' },
    { key: 'mann', name: 'Mann-Whitney', description: 'Comparación no paramétrica entre dos grupos.', category: 'Pruebas', icon: 'M' },
    { key: 'reduction', name: 'Reducción', description: 'PCA y reducción dimensional para explorar patrones.', category: 'Modelamiento', icon: '◇' },
    { key: 'dbscan', name: 'DBSCAN', description: 'Detección de agrupaciones y observaciones atípicas.', category: 'Clustering', icon: '⬡' },
    { key: 'review', name: 'Revisión de clusters', description: 'Calidad, ruido, tamaños y recomendación.', category: 'Clustering', icon: '✓' }
  ];

  readonly selectedAnalysisData = computed(() =>
    this.analyses.find(item => item.key === this.selectedAnalysis()) ?? this.analyses[0]
  );

  constructor() {
    void this.refreshDatasets();
    void this.refreshRuns();
  }

  toggleSidebar(): void { this.sidebarCollapsed.update(value => !value); }
  selectAnalysis(key: AnalysisKey): void { this.selectedAnalysis.set(key); }

  showToast(message: string, duration = 2800): void {
    this.toast.set(message);
    window.setTimeout(() => this.toast.set(''), duration);
  }

  async refreshDatasets(): Promise<void> {
    this.loadingDatasets.set(true);
    try {
      const response = await firstValueFrom(this.http.get<{datasets: DatasetItem[]}>('/api/datasets'));
      this.datasets.set(response.datasets ?? []);
      const current = this.selectedDataset();
      if (!current || !response.datasets.some(d => d.key === current)) {
        this.selectedDataset.set(response.datasets[0]?.key ?? '');
      }
    } catch (error) {
      this.showToast(this.errorMessage(error, 'No fue posible cargar los datasets.'));
    } finally {
      this.loadingDatasets.set(false);
    }
  }

  async uploadFiles(files: FileList | File[]): Promise<void> {
    const list = Array.from(files as ArrayLike<File>);
    if (!list.length) return;
    const form = new FormData();
    list.forEach(file => form.append('files', file, file.name));
    try {
      const response = await firstValueFrom(this.http.post<{datasets: DatasetItem[]}>('/api/datasets/upload', form));
      this.datasets.set(response.datasets ?? []);
      if (!this.selectedDataset() && response.datasets.length) this.selectedDataset.set(response.datasets[0].key);
      this.showToast(`${list.length} archivo(s) cargado(s).`);
    } catch (error) {
      this.showToast(this.errorMessage(error, 'No fue posible cargar los archivos.'));
    }
  }

  getDataset(key: string): DatasetItem | undefined {
    return this.datasets().find(item => item.key === key);
  }

  getColumns(key: string): string[] {
    return this.getDataset(key)?.columnNames ?? [];
  }

  getCategories(key: string, column: string): string[] {
    return (this.getDataset(key)?.categories?.[column] ?? []).map(value => String(value));
  }

  async runAnalysis(params: Record<string, unknown>): Promise<boolean> {
    if (this.analysisRunning()) return false;
    this.analysisRunning.set(true);
    try {
      const run = await firstValueFrom(this.http.post<AnalysisRun>('/api/run', {
        analysis: this.selectedAnalysis(),
        params
      }));
      this.currentRun.set(run);
      this.runs.update(items => [run, ...items.filter(item => item.id !== run.id)]);
      this.showToast(`${this.selectedAnalysisData().name} finalizado.`);
      return true;
    } catch (error) {
      this.showToast(this.errorMessage(error, 'El análisis falló. Revisa los parámetros.'));
      return false;
    } finally {
      this.analysisRunning.set(false);
    }
  }

  async refreshRuns(): Promise<void> {
    try {
      const response = await firstValueFrom(this.http.get<{runs: AnalysisRun[]}>('/api/runs'));
      this.runs.set(response.runs ?? []);
      if (!this.currentRun() && response.runs.length) this.currentRun.set(response.runs[0]);
    } catch { /* El historial no bloquea la aplicación. */ }
  }

  async selectRun(id: string): Promise<void> {
    try {
      const run = await firstValueFrom(this.http.get<AnalysisRun>(`/api/runs/${id}`));
      this.currentRun.set(run);
    } catch (error) {
      this.showToast(this.errorMessage(error, 'No fue posible abrir la corrida.'));
    }
  }

  async askAssistant(): Promise<void> {
    if (!this.question().trim()) {
      this.assistantMessage.set('Escribe una pregunta para poder orientarte.');
      return;
    }
    this.assistantLoading.set(true);
    this.assistantMessage.set('Analizando tu pregunta…');
    try {
      const response = await firstValueFrom(this.http.post<{text?: string; error?: string}>('/api/ask', {
        question: this.question(),
        dataset: this.selectedDataset(),
        provider: 'local',
        model: 'phi4-mini-reasoning'
      }));
      this.assistantMessage.set(response.text || response.error || 'No se recibió respuesta.');
    } catch (error) {
      this.assistantMessage.set(this.errorMessage(error, 'El asistente no pudo responder.'));
    } finally {
      this.assistantLoading.set(false);
    }
  }

  private errorMessage(error: unknown, fallback: string): string {
    const value = error as { error?: { error?: string }, message?: string };
    return value?.error?.error || value?.message || fallback;
  }
}
