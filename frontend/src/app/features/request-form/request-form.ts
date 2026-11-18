import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { failure, label, Schema, Workspace } from '../../core/workspace';

export function textLength(min: number, max: number): ValidatorFn {
  return control => {
    const n = String(control.value ?? '').trim().length;
    return n >= min && n <= max ? null : {length: true};
  };
}

@Component({ selector:'app-request-form', imports:[ReactiveFormsModule,RouterLink], templateUrl:'./request-form.html' })
export class RequestForm {
  readonly ws = inject(Workspace);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder).nonNullable;
  readonly id = inject(ActivatedRoute).snapshot.paramMap.get('id');
  readonly base = signal<Schema['RequestDetail'] | null>(null);
  readonly error = signal('');
  readonly busy = signal(false);
  readonly step = signal(1);
  readonly required = signal<Schema['EvidenceKind'][] | null>(null);
  readonly checklistError = signal(false);
  private generation = 0;
  readonly label = label;
  readonly kinds: Schema['EvidenceKind'][] = ['business_registration','security_questionnaire','service_sla'];
  readonly form = this.fb.group({
    vendor_name: ['',textLength(2,120)], requester_department: ['',textLength(1,120)],
    service_category: this.fb.control<Schema['Category']>('consulting', Validators.required),
    business_criticality: this.fb.control<Schema['Criticality']>('low', Validators.required),
    sensitive_data_access: false, service_description: ['',textLength(1,4000)],
    evidence: this.fb.group({ business_registration: false, security_questionnaire: false, service_sla: false }),
  });
  constructor() { if (this.id) void this.load(); else void this.checklist(); }
  async load() {
    this.busy.set(true);
    try {
      const row = await this.ws.get<Schema['RequestDetail']>('requests/'+this.id);
      this.base.set(row);
      const {vendor_name, requester_department, service_category, business_criticality, sensitive_data_access, service_description} = row;
      this.form.patchValue({vendor_name, requester_department, service_category, business_criticality, sensitive_data_access, service_description});
      this.form.controls.evidence.reset();
      for (const item of row.evidence ?? []) this.form.controls.evidence.controls[item.kind].setValue(item.present);
      await this.checklist();
    } catch(err) { this.error.set(failure(err)); } finally { this.busy.set(false); }
  }
  async checklist() {
    const generation = ++this.generation;
    this.checklistError.set(false); this.required.set(null);
    const v = this.form.getRawValue();
    try {
      const result = await this.ws.get<Schema['EvidenceKind'][]>(`settings/evidence?category=${v.service_category}&criticality=${v.business_criticality}`);
      if (generation === this.generation) this.required.set(result);
    } catch { if(generation === this.generation) this.checklistError.set(true); }
  }
  next() {
    const c = this.form.controls;
    const group = this.step() === 1 ? [c.vendor_name,c.requester_department] : [c.service_description];
    group.forEach(field => field.markAsTouched());
    if(group.every(field => field.valid)) this.step.update(n => n+1);
  }
  async save() {
    if(this.busy() || this.form.invalid || this.ws.persona() !== 'Requester') return;
    this.busy.set(true); this.error.set('');
    const {evidence, ...fields} = this.form.getRawValue();
    const body = {...fields, evidence: this.kinds.map(kind=>({
      kind, present: evidence[kind], pointer: this.base()?.evidence?.find(e=>e.kind === kind)?.pointer ?? null,
    }))};
    try {
      const row = this.base();
      const saved = row ? await this.ws.write<Schema['RequestView']>('PATCH','requests/'+row.id,{...body,expected_version:row.version} satisfies Schema['EditRequest'])
        : await this.ws.write<Schema['RequestView']>('POST','requests',{...body,expected_version:0} satisfies Schema['CreateRequest']);
      await this.router.navigate(['/requests',saved.id]);
    } catch(err) {
      this.error.set(failure(err));
      if(err instanceof HttpErrorResponse && err.status===409 && this.id) await this.load();
    } finally { this.busy.set(false); }
  }
}
