import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnDestroy, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { failure, label, Schema, Workspace } from '../../core/workspace';
import { RiskBadge, StatusBadge } from '../../shared/badges';

@Component({
  selector: 'app-request-detail',
  imports: [DatePipe, RouterLink, ReactiveFormsModule, StatusBadge, RiskBadge],
  templateUrl: './request-detail.html',
})
export class RequestDetail implements OnDestroy {
  readonly ws = inject(Workspace);
  readonly path = 'requests/' + inject(ActivatedRoute).snapshot.paramMap.get('id');
  readonly row = signal<Schema['RequestDetail'] | null>(null);
  readonly events = signal<Schema['AuditView'][]>([]);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly timedOut = signal(false);
  readonly label = label;
  readonly form = inject(FormBuilder).nonNullable.group({
    reviewer_label: [
      'Demo reviewer',
      [Validators.required, Validators.pattern(/\S/), Validators.maxLength(120)],
    ],
    reason: ['', [Validators.required, Validators.pattern(/\S/), Validators.maxLength(4000)]],
    confirmed: false,
  });
  private stopped = false;
  private timer?: ReturnType<typeof setTimeout>;
  private deadline = 0;
  constructor() {
    void this.refresh();
  }
  ngOnDestroy() {
    this.stopped = true;
    clearTimeout(this.timer);
  }
  async refresh() {
    this.deadline = Date.now() + 60000;
    this.timedOut.set(false);
    this.error.set('');
    await this.load();
  }
  private async load() {
    clearTimeout(this.timer);
    try {
      const [row, events] = await Promise.all([
        this.ws.get<Schema['RequestDetail']>(this.path),
        this.ws.get<Schema['AuditView'][]>(this.path + '/audit'),
      ]);
      if (this.stopped) return;
      this.row.set(row);
      this.events.set(events);
      if (['UNDER_REVIEW', 'JIRA_PENDING'].includes(row.status)) {
        if (Date.now() >= this.deadline) this.timedOut.set(true);
        else this.timer = setTimeout(() => void this.load(), 1200);
      }
    } catch (err) {
      this.error.set(failure(err));
    }
  }
  async act(
    kind: 'submit' | 'decision' | 'jira/reconcile',
    action?: Schema['HumanDecision']['action'],
  ) {
    const row = this.row();
    if (!row || this.busy()) return;
    if (kind === 'submit' ? this.ws.persona() !== 'Requester' : this.ws.persona() !== 'Reviewer')
      return;
    const v = this.form.getRawValue();
    let body: Schema['Versioned'] | Schema['HumanDecision'] | Schema['Reconcile'] = {
      expected_version: row.version,
    };
    if (kind === 'decision') {
      this.form.markAllAsTouched();
      if (!action || this.form.invalid) return;
      body = {
        ...body,
        action,
        reviewer_label: v.reviewer_label.trim(),
        reason: v.reason.trim(),
      } satisfies Schema['HumanDecision'];
    } else if (kind === 'jira/reconcile') {
      this.form.controls.reviewer_label.markAsTouched();
      if (this.form.controls.reviewer_label.invalid) return;
      body = {
        ...body,
        reviewer_label: v.reviewer_label.trim(),
        checked_jira_and_no_issue_exists: v.confirmed,
      } satisfies Schema['Reconcile'];
    }
    this.busy.set(true);
    this.error.set('');
    try {
      await this.ws.write<Schema['RequestView']>('POST', this.path + '/' + kind, body);
      this.form.controls.confirmed.reset();
      await this.refresh();
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 409) {
        await this.refresh();
        this.form.controls.confirmed.reset();
      }
      this.error.set(failure(err));
    } finally {
      this.busy.set(false);
    }
  }
}
