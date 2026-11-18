import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Workspace, Schema, label, failure } from '../../core/workspace';
import { StatusBadge, RiskBadge } from '../../shared/badges';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, DatePipe, StatusBadge, RiskBadge],
  templateUrl: './dashboard.html',
})
export class Dashboard {
  readonly workspace = inject(Workspace);
  readonly queue = Boolean(inject(ActivatedRoute).snapshot.data['queue']);
  readonly data = signal<Schema['RequestList'] | null>(null);
  readonly error = signal('');
  readonly filter = signal('');
  readonly label = label;
  readonly keys = Object.keys;
  constructor() {
    void this.load();
  }
  async load() {
    this.error.set('');
    try {
      this.data.set(
        await this.workspace.get<Schema['RequestList']>(
          'requests' + (this.queue ? '?status=AWAITING_APPROVAL' : ''),
        ),
      );
    } catch (err) {
      this.error.set(failure(err));
    }
  }
  count(status: string) {
    return this.data()?.counts[status] ?? 0;
  }
  total() {
    return Object.values(this.data()?.counts ?? {}).reduce((a, b) => a + (b ?? 0), 0);
  }
}
