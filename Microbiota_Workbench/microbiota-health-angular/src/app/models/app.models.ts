export type AnalysisKey =
  | 'exploration' | 'characterization' | 'normality' | 'correlation'
  | 'visualization' | 'kde' | 'kruskal' | 'mann'
  | 'reduction' | 'dbscan' | 'review';

export interface DatasetItem {
  id: number;
  key: string;
  name: string;
  rows: number;
  columns: number;
  status: 'Listo' | 'Procesando';
  type: string;
  columnNames: string[];
  numericColumns: string[];
  categoricalColumns: string[];
  categories: Record<string, Array<string | number | boolean | null>>;
}

export interface AnalysisItem {
  key: AnalysisKey;
  name: string;
  description: string;
  category: string;
  icon: string;
}

export interface ResultTable {
  name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
  truncated?: boolean;
}

export interface ResultFigure {
  name: string;
  url: string;
}

export interface AnalysisRun {
  id: string;
  analysis: AnalysisKey;
  backendAnalysis?: string;
  createdAt: string;
  parameters: Record<string, unknown>;
  tables: ResultTable[];
  figures: ResultFigure[];
  result?: unknown;
}
