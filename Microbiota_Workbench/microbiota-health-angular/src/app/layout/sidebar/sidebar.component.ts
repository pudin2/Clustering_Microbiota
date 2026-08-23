import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';
import { WorkbenchStateService } from '../../services/workbench-state.service';
import { AnalysisKey } from '../../models/app.models';

@Component({ selector:'app-sidebar', standalone:true, imports:[RouterLink, RouterLinkActive], templateUrl:'./sidebar.component.html', styleUrl:'./sidebar.component.css' })
export class SidebarComponent {
  readonly state = inject(WorkbenchStateService);
  private readonly router = inject(Router);
  openAnalysis(key: AnalysisKey): void { this.state.selectAnalysis(key); void this.router.navigate(['/analisis', key]); }
}
