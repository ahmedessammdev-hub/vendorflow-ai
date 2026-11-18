import { Component, input } from '@angular/core';
import { label, Schema } from '../core/workspace';

@Component({
  selector: 'app-status',
  template: '<span class="pill" [attr.data-tone]="status()">{{ label(status()) }}</span>',
})
export class StatusBadge {
  readonly status = input.required<Schema['Status']>();
  readonly label = label;
}
@Component({
  selector: 'app-risk',
  template: '<span class="pill" [attr.data-tone]="risk().band">{{ label(risk().band) }} · {{ risk().score }}</span>',
})
export class RiskBadge {
  readonly risk = input.required<Schema['Risk']>();
  readonly label = label;
}
