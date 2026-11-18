import { TestBed } from '@angular/core/testing';
import { FormControl } from '@angular/forms';
import { RiskBadge, StatusBadge } from './badges';
import { textLength } from '../features/request-form/request-form';

describe('Supplier workflow',()=>{
  it('rejects short, whitespace-only and oversized trimmed names',()=>{
    const name=new FormControl('',textLength(2,120));
    for(const bad of [' ',' a ','x'.repeat(121)]) {name.setValue(bad); expect(name.valid).toBe(false);}
    name.setValue(' Cedar '); expect(name.valid).toBe(true);
  });
  it('shows risk band and points as text',()=>{
    const f=TestBed.createComponent(RiskBadge);
    f.componentRef.setInput('risk',{score:6,band:'HIGH',factors:[]}); f.detectChanges();
    expect(f.nativeElement.textContent).toContain('High · 6');
  });
  it('names the human approval status',()=>{
    const f=TestBed.createComponent(StatusBadge);
    f.componentRef.setInput('status','AWAITING_APPROVAL'); f.detectChanges();
    expect(f.nativeElement.textContent).toContain('Awaiting approval');
  });
});
