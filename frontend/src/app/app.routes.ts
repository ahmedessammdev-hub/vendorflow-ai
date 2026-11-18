import { Routes } from '@angular/router';
import { Dashboard } from './features/dashboard/dashboard';
import { RequestForm } from './features/request-form/request-form';
import { RequestDetail } from './features/request-detail/request-detail';
import { Metrics } from './features/metrics/metrics';

export const routes: Routes = [
  {path: '', component: Dashboard, title: 'Dashboard | VendorFlow'},
  {path: 'queue', component: Dashboard, data: {queue: true}, title: 'Review queue | VendorFlow'},
  {path: 'requests/new', component: RequestForm, title: 'New request | VendorFlow'},
  {path: 'requests/:id/edit', component: RequestForm, title: 'Edit request | VendorFlow'},
  {path: 'requests/:id', component: RequestDetail, title: 'Request details | VendorFlow'},
  {path: 'metrics', component: Metrics, title: 'Metrics | VendorFlow'},
  {path: '**', redirectTo: ''},
];
