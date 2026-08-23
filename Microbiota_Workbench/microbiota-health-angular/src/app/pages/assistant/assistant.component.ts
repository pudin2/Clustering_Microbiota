import { Component,inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { WorkbenchStateService } from '../../services/workbench-state.service';
@Component({selector:'app-assistant',standalone:true,imports:[FormsModule],templateUrl:'./assistant.component.html',styleUrl:'./assistant.component.css'})
export class AssistantComponent{readonly state=inject(WorkbenchStateService);}
