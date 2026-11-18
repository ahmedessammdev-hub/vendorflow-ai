import { Component, inject, signal } from '@angular/core';
import { KeyValuePipe } from '@angular/common';
import { failure, label, Schema, Workspace } from '../../core/workspace';

@Component({ selector: 'app-metrics', imports: [KeyValuePipe], template: `
<div class="pagehead"><div><p class="eyebrow">Workspace activity</p><h1>Metrics</h1></div><button (click)="load()">Refresh</button></div>
@if (error()) {<p class="notice" role="alert">{{ error() }}</p>}
@if (data(); as m) {
<div class="stats"><article><span>LLM call records</span><strong>{{ m.calls }}</strong></article><article><span>Median latency (ms)</span><strong>{{ m.latency_p50_ms ?? '—' }}</strong></article><article><span>p95 latency (ms)</span><strong>{{ m.latency_p95_ms ?? '—' }}</strong></article></div>
<div class="grid"><section class="panel"><h2>Requests by status</h2>@for (r of m.requests | keyvalue; track r.key){<p class="pair"><span>{{ label(r.key) }}</span><b>{{ r.value }}</b></p>} @empty {<p>No requests yet.</p>}</section>
<section class="panel"><h2>Jira operations</h2>@for (r of m.jira | keyvalue; track r.key){<p class="pair"><span>{{ label(r.key) }}</span><b>{{ r.value }}</b></p>} @empty {<p>No delivery attempts yet.</p>}</section>
<section class="panel"><h2>Reported tokens</h2><p class="pair">Input <b>{{ m.tokens_in ?? 'Unavailable' }}</b></p><p class="pair">Output <b>{{ m.tokens_out ?? 'Unavailable' }}</b></p></section></div>
} @else if (!error()) {<div class="skeleton" role="status">Loading metrics…</div>}` })
export class Metrics {
  readonly workspace = inject(Workspace);
  readonly data = signal<Schema['WorkspaceMetrics'] | null>(null);
  readonly error = signal('');
  readonly label = label;
  constructor() { void this.load(); }
  async load() {
    this.error.set('');
    try { this.data.set(await this.workspace.get<Schema['WorkspaceMetrics']>('metrics')); }
    catch (err) { this.error.set(failure(err)); }
  }
}
