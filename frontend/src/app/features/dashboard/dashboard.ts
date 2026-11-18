import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Workspace, Schema, label, failure } from '../../core/workspace';
import { StatusBadge, RiskBadge } from '../../shared/badges';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, DatePipe, StatusBadge, RiskBadge],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard {
  readonly workspace = inject(Workspace);
  readonly queue = Boolean(inject(ActivatedRoute).snapshot.data['queue']);
  readonly data = signal<Schema['RequestList'] | null>(null);
  readonly error = signal('');
  readonly filter = signal('');
  readonly query = signal('');
  readonly label = label;
  readonly keys = Object.keys;
  readonly visible = computed(() => {
    const q = this.query().trim().toLowerCase();
    return (this.data()?.items ?? []).filter(
      (row) =>
        (!this.filter() || this.filter() === row.status) &&
        [row.vendor_name, row.requester_department, label(row.service_category)].some((v) =>
          v.toLowerCase().includes(q),
        ),
    );
  });
  readonly pipeline = computed(() => {
    const counts = this.data()?.counts ?? {};
    const sum = (...states: Schema['Status'][]) => states.reduce((n, s) => n + (counts[s] ?? 0), 0);
    return [
      { name: 'Intake', value: sum('DRAFT', 'NEEDS_CHANGES') },
      { name: 'In review', value: sum('SUBMITTED', 'UNDER_REVIEW', 'AWAITING_APPROVAL') },
      {
        name: 'Decided',
        value: sum('APPROVED', 'REJECTED', 'JIRA_PENDING', 'JIRA_CREATED', 'JIRA_FAILED'),
      },
    ];
  });
  readonly riskMix = computed(() =>
    (['HIGH', 'MEDIUM', 'LOW'] as const).map((band) => ({
      band,
      value: this.data()?.items.filter((row) => row.risk.band === band).length ?? 0,
    })),
  );
  readonly total = computed(() => this.pipeline().reduce((n, g) => n + g.value, 0));
  initials(name: string) {
    return name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => Array.from(word)[0])
      .join('')
      .toUpperCase();
  }
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
}
