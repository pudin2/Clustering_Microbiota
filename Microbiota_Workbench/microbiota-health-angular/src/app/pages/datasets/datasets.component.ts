import { Component, ElementRef, ViewChild, inject } from '@angular/core';
import { WorkbenchStateService } from '../../services/workbench-state.service';

@Component({selector:'app-datasets',standalone:true,templateUrl:'./datasets.component.html',styleUrl:'./datasets.component.css'})
export class DatasetsComponent {
  readonly state = inject(WorkbenchStateService);
  @ViewChild('fileInput') fileInput?: ElementRef<HTMLInputElement>;
  chooseFiles(): void { this.fileInput?.nativeElement.click(); }
  async onFiles(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (input.files) await this.state.uploadFiles(input.files);
    input.value = '';
  }
  selectDataset(key: string): void {
    this.state.selectedDataset.set(key);
    this.state.showToast('Dataset principal actualizado.');
  }
}
