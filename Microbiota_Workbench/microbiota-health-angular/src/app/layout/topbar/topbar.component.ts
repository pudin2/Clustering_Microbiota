import { Component, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';
import { WorkbenchStateService } from '../../services/workbench-state.service';
@Component({selector:'app-topbar',standalone:true,templateUrl:'./topbar.component.html',styleUrl:'./topbar.component.css'})
export class TopbarComponent {
  readonly state=inject(WorkbenchStateService); private router=inject(Router); readonly url=signal(this.router.url);
  readonly title=computed(()=>{const u=this.url();if(u.startsWith('/datasets'))return 'Gestión de datasets';if(u.startsWith('/analisis'))return this.state.selectedAnalysisData().name;if(u.startsWith('/asistente'))return 'Asistente académico';if(u.startsWith('/resultados'))return 'Resultados e historial';return 'Centro de investigación';});
  constructor(){this.router.events.pipe(filter((e):e is NavigationEnd=>e instanceof NavigationEnd)).subscribe(e=>this.url.set(e.urlAfterRedirects));}
}
