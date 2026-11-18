import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('Application shell', () => {
  beforeEach(() => TestBed.configureTestingModule({
    imports: [App],
    providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
  }));

  it('renders the demo warning and the integration modes returned by the API', () => {
    const fixture = TestBed.createComponent(App);
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/settings/integrations').flush({
      authentication: 'none', llm_mode: 'unavailable', jira_mode: 'simulation',
    });
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Demo mode: no authentication');
    expect(text).toContain('Unavailable');
    expect(text).toContain('Simulation');
    http.verify();
  });

  it('offers a retry when integration settings cannot be loaded', () => {
    const fixture = TestBed.createComponent(App);
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/settings/integrations').flush(null, {status: 503, statusText: 'Offline'});
    fixture.detectChanges();
    const element: HTMLElement = fixture.nativeElement;
    element.querySelector('button')!.click();
    http.expectOne('/api/settings/integrations').flush({
      authentication: 'none', llm_mode: 'configured', jira_mode: 'live',
    });
    fixture.detectChanges();
    expect(element.textContent).toContain('Configured');
    expect(element.textContent).toContain('Live');
    http.verify();
  });
});
