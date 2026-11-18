import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { components } from './api.generated';

export type Schema = components['schemas'];
export type Persona = 'Requester' | 'Reviewer';
export function label(value: string): string {
  const words = value.toLowerCase().replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function failure(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 409) return 'This request changed. The latest version has been loaded. Review it before trying again.';
    if (error.status === 422) return 'Check the values you entered and try again.';
    if (error.status === 404) return 'Request not found. Return to the dashboard.';
  }
  return 'Could not reach the local API. Check the connection and retry.';
}

@Injectable({ providedIn: 'root' })
export class Workspace {
  readonly http = inject(HttpClient);
  readonly persona = signal<Persona>(sessionStorage.getItem('persona') === 'Reviewer' ? 'Reviewer' : 'Requester');
  switchPersona(value: string) {
    const persona = value === 'Reviewer' ? 'Reviewer' : 'Requester';
    this.persona.set(persona);
    sessionStorage.setItem('persona', persona);
  }
  get<T>(path: string) {
    return firstValueFrom(this.http.get<T>('/api/' + path, { timeout: 8000 }));
  }
  write<T>(method: 'POST' | 'PATCH', path: string, body: unknown) {
    return firstValueFrom(this.http.request<T>(method, '/api/' + path, {body, timeout: 12000}));
  }
}
