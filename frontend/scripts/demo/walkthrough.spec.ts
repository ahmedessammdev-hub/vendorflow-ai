import { test, expect } from '@playwright/test';
import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import fixtures from '../../../sample_data/requests.json' with { type: 'json' };
test('record isolated synthetic onboarding', async ({ page }) => {
  const dir = resolve(import.meta.dirname, '../../../.runtime/film');
  mkdirSync(dir, { recursive: true });
  const frames = ['ffconcat version 1.0'],
    subtitles: string[] = [];
  let elapsed = 0,
    index = 0;
  const stamp = (ms: number) => new Date(ms).toISOString().slice(11, 23).replace('.', ',');
  async function snap(duration: number) {
    const file = 'shot-' + String(++index).padStart(4, '0') + '.jpg';
    await page.screenshot({ path: join(dir, file), quality: 88, type: 'jpeg' });
    frames.push("file '" + file + "'", 'duration ' + duration);
    elapsed += Math.round(duration * 1000);
  }
  async function scene(caption: string, act: () => Promise<unknown>, seconds: number) {
    const start = elapsed;
    let done = false;
    const action = act().finally(() => {
      done = true;
    });
    const capture = async () => {
      while (!done) {
        await snap(0.32);
        await page.waitForTimeout(200);
      }
    };
    await Promise.all([action, capture()]);
    await page.waitForTimeout(400);
    await snap(Math.max(3, seconds - (elapsed - start) / 1000));
    subtitles.push(
      String(subtitles.length / 4 + 1),
      stamp(start) + ' --> ' + stamp(elapsed),
      caption,
      '',
    );
  }
  const heading = (name: string) =>
    page
      .getByRole('heading', { name, exact: true })
      .evaluate((e) => e.scrollIntoView({ block: 'center' }));
  const link = (name: string) => page.getByRole('link', { name, exact: true }).first().click();
  const button = (name: string) => page.getByRole('button', { name, exact: true }).click();
  const status = (name: string) => expect(page.locator('app-status')).toHaveText(name);
  await page.goto('/');
  await expect(page.getByText('Unavailable', { exact: true })).toBeVisible();
  for (const item of fixtures) {
    expect((await page.request.post('/api/requests', { data: item })).status()).toBe(201);
  }
  await page.reload();
  await expect(page.getByRole('link', { name: 'Cedar Cloud Services' })).toBeVisible();
  await scene(
    'VendorFlow AI  |  Supplier onboarding review\nSynthetic suppliers  /  Jira simulation',
    async () => {},
    8,
  );
  await scene(
    'The requester opens a draft describing a cloud hosting service.',
    async () => {
      await link('Cedar Cloud Services');
      await heading('Cedar Cloud Services');
    },
    8,
  );
  await scene(
    'The evidence checklist records declarations supplied by the requester.',
    () => heading('Evidence'),
    7,
  );
  await scene(
    'Submission runs the completeness checks and starts the review graph.',
    async () => {
      await button('Submit for review');
      await status('Awaiting approval');
    },
    8,
  );
  await scene(
    'Criticality, data access and service category contribute to the illustrative risk score.',
    () => heading('Illustrative risk'),
    8,
  );
  await scene(
    'The summary and recommendation have separate outcomes.\nThis offline walkthrough has no model configured.',
    () => heading('AI assessment'),
    9,
  );
  await scene(
    'The graph pauses. Jira has no operation while a human decision is pending.',
    () => heading('Jira delivery'),
    8,
  );
  await scene(
    'The reviewer opens the queue and selects the supplier.',
    async () => {
      await page.getByLabel('Persona').selectOption('Reviewer');
      await link('Review queue');
      await expect(page.getByRole('link', { name: 'Cedar Cloud Services' })).toBeVisible();
    },
    8,
  );
  await scene(
    'The reviewer records the reason for the decision.',
    async () => {
      await link('Cedar Cloud Services');
      await page
        .getByLabel('Decision reason')
        .pressSequentially('Reviewed the declared evidence for this synthetic hosting service.', {
          delay: 36,
        });
    },
    10,
  );
  await scene(
    'Approval queues delivery. The simulated issue has a plain-text SIM key.',
    async () => {
      await button('Approve');
      await expect(page.getByText('SIM-1', { exact: true })).toBeVisible();
      await heading('Jira delivery');
    },
    9,
  );
  await scene(
    'The audit timeline preserves the reviewer decision and subsequent delivery.',
    () => heading('Audit timeline'),
    8,
  );
  await scene(
    'Northstar follows a different path. Its draft is missing required evidence.',
    async () => {
      await page.getByLabel('Persona').selectOption('Requester');
      await link('Dashboard');
      await link('Northstar Advisory');
      await button('Submit for review');
      await status('Needs changes');
      await heading('Evidence');
    },
    9,
  );
  await scene(
    'The requester can return to the form and supply the missing declarations.',
    async () => {
      await link('Edit request');
      await button('Continue');
      await button('Continue');
    },
    8,
  );
  await scene(
    'Metrics show what happened in this workspace, including simulated Jira delivery.',
    async () => {
      await link('Metrics');
      await heading('Jira operations');
    },
    12,
  );
  frames.push(frames[frames.length - 2]);
  writeFileSync(join(dir, 'frames.txt'), frames.join('\n') + '\n');
  writeFileSync(join(dir, 'captions.srt'), subtitles.join('\n') + '\n');
  const outputDir = resolve(import.meta.dirname, '../../../docs/demo');
  mkdirSync(outputDir, { recursive: true });
  const filter =
    "fps=12,pad=1440:1016:0:0:color=0x102820,setsar=1,subtitles=captions.srt:force_style='FontName=Segoe UI,FontSize=9,Outline=0,Shadow=0,MarginV=8,PrimaryColour=&H00FFFFFF'";
  execFileSync(
    'ffmpeg',
    [
      '-hide_banner',
      '-loglevel',
      'error',
      '-y',
      '-f',
      'concat',
      '-safe',
      '0',
      '-i',
      'frames.txt',
      '-vf',
      filter,
      '-c:v',
      'libx264',
      '-preset',
      'fast',
      '-crf',
      '19',
      '-pix_fmt',
      'yuv420p',
      '-t',
      String(elapsed / 1000),
      '-movflags',
      '+faststart',
      join(dir, 'encoded.mp4'),
    ],
    { cwd: dir, stdio: 'inherit' },
  );
  renameSync(join(dir, 'encoded.mp4'), join(outputDir, 'vendorflow-demo.mp4'));
  console.log('Recorded', index, 'frames;', elapsed / 1000, 'seconds.');
});
