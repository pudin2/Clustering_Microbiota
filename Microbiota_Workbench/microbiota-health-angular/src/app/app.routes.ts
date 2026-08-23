import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home/home.component';
import { DatasetsComponent } from './pages/datasets/datasets.component';
import { AnalysisComponent } from './pages/analysis/analysis.component';
import { AssistantComponent } from './pages/assistant/assistant.component';
import { ResultsComponent } from './pages/results/results.component';

export const appRoutes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'inicio' },
  { path: 'inicio', component: HomeComponent, title: 'Centro de investigación' },
  { path: 'datasets', component: DatasetsComponent, title: 'Gestión de datasets' },
  { path: 'analisis', component: AnalysisComponent, title: 'Análisis' },
  { path: 'analisis/:analysisKey', component: AnalysisComponent, title: 'Análisis' },
  { path: 'asistente', component: AssistantComponent, title: 'Asistente académico' },
  { path: 'resultados', component: ResultsComponent, title: 'Resultados e historial' },
  { path: '**', redirectTo: 'inicio' }
];
