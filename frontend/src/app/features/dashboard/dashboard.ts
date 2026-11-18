import { Component } from '@angular/core';

@Component({
  selector: 'app-dashboard',
  template: `
    <h1>Dashboard</h1>
    <section aria-labelledby="requests-heading">
      <h2 id="requests-heading">Supplier requests</h2>
      <p>Request intake will be available in a later phase.</p>
    </section>
  `,
  styles: `
    h1 { margin: clamp(2.5rem, 6vw, 5rem) 0 1.5rem; font-size: clamp(2.3rem, 6vw, 4rem); font-weight: 550; letter-spacing: -.055em; }
    section { padding: clamp(1.4rem, 4vw, 2.8rem); background: #fff; border: 1px solid #d7dfd8; border-radius: .8rem; }
    h2 { margin: 0 0 .65rem; font-size: 1.35rem; }
    p { margin: 0; color: #536458; line-height: 1.6; }
  `,
})
export class Dashboard {}
