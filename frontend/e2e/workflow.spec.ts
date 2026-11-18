import { expect, test, Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

async function capture(page: Page, name: string) {
  const dir = resolve(process.env['VENDORFLOW_SCREENSHOTS'] ?? '../docs/screenshots');
  await mkdir(dir, { recursive: true });
  await page.screenshot({ path: resolve(dir, name + '.png'), fullPage: true });
  const result = await new AxeBuilder({ page }).analyze();
  const severe = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  console.log('axe', name, 'serious/critical', severe.length);
  expect(severe.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) }))).toEqual([]);
}

async function draft(page: Page, name: string, complete: boolean) {
  await page.goto('/');
  await expect(page.getByText('Unavailable', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'New request' }).click();
  await page.getByLabel('Supplier name').fill(name);
  await page.getByLabel('Requester department').fill('Procurement');
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Service category').selectOption('cloud_hosting');
  await page.getByLabel('Business criticality').selectOption('high');
  await page
    .getByLabel('Service description')
    .fill('Synthetic managed hosting for business records.');
  await page.getByLabel('Access to sensitive data').check();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Business registration').check();
  await page.getByLabel('Security questionnaire').check();
  if (complete) {
    await page.getByLabel('Service sla').check();
    await capture(page, 'request-form');
  }
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
  await page.getByRole('button', { name: 'Submit for review' }).click();
}

test('Cedar approval creates one simulated issue and survives reload', async ({ page }) => {
  await draft(page, 'Cedar Cloud Services', true);
  await expect(page.locator('app-status')).toHaveText('Awaiting approval');
  await page.getByLabel('Persona').selectOption('Reviewer');
  await page.getByRole('link', { name: 'Review queue' }).click();
  await expect(page.getByRole('link', { name: 'Cedar Cloud Services' })).toBeVisible();
  await capture(page, 'review-queue');
  await page.getByRole('link', { name: 'Cedar Cloud Services' }).click();
  const requestPath = '/api' + new URL(page.url()).pathname;
  const before = await (await page.request.get(requestPath)).json();
  await page
    .getByLabel('Decision reason')
    .fill('Reviewed the declared evidence for this synthetic scenario.');
  await page.getByRole('button', { name: 'Approve', exact: true }).click();
  await expect(page.getByText('SIM-1', { exact: true })).toBeVisible();
  const replay = await page.request.post(requestPath + '/decision', {
    data: {
      expected_version: before.version,
      action: 'approve',
      reviewer_label: 'Test reviewer',
      reason: 'Duplicate submission',
    },
  });
  expect(replay.status()).toBe(409);
  await page.reload();
  await expect(page.getByText('SIM-1', { exact: true })).toBeVisible();
  expect((await (await page.request.get(requestPath)).json()).jira.attempts).toBe(1);
  await expect(page.getByRole('link', { name: 'SIM-1' })).toHaveCount(0);
  await capture(page, 'request-detail');
  await page.getByRole('link', { name: 'Dashboard', exact: true }).first().click();
  await expect(page.getByRole('link', { name: 'Cedar Cloud Services' })).toBeVisible();
  await capture(page, 'dashboard');
  const search = page.getByRole('searchbox', { name: 'Search suppliers' });
  const status = page.getByRole('combobox', { name: 'Status', exact: true });
  await status.selectOption('JIRA_CREATED');
  await search.fill('cedar');
  await expect(page.getByRole('link', { name: 'Cedar Cloud Services' })).toBeVisible();
  await status.selectOption('DRAFT');
  await expect(page.getByText('No suppliers match these filters.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(search).toHaveValue('');
  await expect(status).toHaveValue('');
  await expect(page.getByRole('link', { name: 'Cedar Cloud Services' })).toBeVisible();
});

test('Northstar corrects missing evidence, reaches review and is rejected without Jira', async ({
  page,
}) => {
  await draft(page, 'Northstar Hosting', false);
  await expect(page.locator('app-status')).toHaveText('Needs changes');
  await expect(page.getByText('Missing', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Edit request' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Service sla').check();
  await page.getByRole('button', { name: 'Save draft' }).click();
  await page.getByRole('button', { name: 'Submit for review' }).click();
  await expect(page.locator('app-status')).toHaveText('Awaiting approval');
  await page.getByLabel('Persona').selectOption('Reviewer');
  await page.getByLabel('Decision reason').fill('Synthetic service outside current scope.');
  await page.getByRole('button', { name: 'Reject', exact: true }).click();
  await expect(page.locator('app-status')).toHaveText('Rejected');
  await expect(page.getByText('No Jira operation recorded.')).toBeVisible();
  await page.getByRole('link', { name: 'Metrics', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Jira operations' })).toBeVisible();
  await capture(page, 'metrics');
});
