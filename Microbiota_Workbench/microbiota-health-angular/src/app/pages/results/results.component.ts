import { Component, inject } from '@angular/core';
import { WorkbenchStateService } from '../../services/workbench-state.service';

@Component({selector:'app-results',standalone:true,templateUrl:'./results.component.html',styleUrl:'./results.component.css'})
export class ResultsComponent {
  readonly state = inject(WorkbenchStateService);
  label(key: string): string {
    return this.state.analyses.find(item => item.key === key)?.name ?? key;
  }
  async openRun(id: string): Promise<void> { await this.state.selectRun(id); }
  stringify(value: unknown): string {
    try { return JSON.stringify(value, null, 2); } catch { return String(value); }
  }
}
