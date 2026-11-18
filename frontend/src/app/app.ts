import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';

import { Workspace } from './core/workspace';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import type { components } from './core/api.generated';

@Component({
  selector: 'app-root',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly workspace = inject(Workspace);
  private readonly http = inject(HttpClient);
  protected readonly modes = signal<components['schemas']['IntegrationModes'] | null>(null);
  protected readonly failed = signal(false);

  constructor() {
    this.loadModes();
  }

  protected focusContent(event: Event): void {
    event.preventDefault();
    document.getElementById('content')?.focus();
  }

  protected loadModes(): void {
    this.failed.set(false);
    this.http
      .get<components['schemas']['IntegrationModes']>('/api/settings/integrations', {
        timeout: 8000,
      })
      .subscribe({
        next: (modes) => this.modes.set(modes),
        error: () => this.failed.set(true),
      });
  }
}
