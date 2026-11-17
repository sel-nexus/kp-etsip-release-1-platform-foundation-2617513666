import { chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

// Capture representative live views for text-based and human visual review.
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(process.env.E2E_BASE_URL || 'http://127.0.0.1:5173');
  await page.getByLabel('Email address').fill('admin@ketsip.local');
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD || '');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.getByRole('link', { name: 'Applications', exact: true }).click();
  await page.getByRole('heading', { name: 'Application repository' }).waitFor();
  const capture = async (name) => {
    const tree = page.accessibility ? await page.accessibility.snapshot() : await page.locator('body').ariaSnapshot();
    const styles = await page.evaluate(() => ({ font: getComputedStyle(document.body).fontFamily, color: getComputedStyle(document.body).color, background: getComputedStyle(document.body).backgroundColor }));
    const html = await page.content();
    await page.screenshot({ path: `test-results/${name}.png`, fullPage: true });
    return `${name}\nACCESSIBILITY\n${JSON.stringify(tree, null, 2)}\nSTYLES\n${JSON.stringify(styles)}\nHTML\n${html}\n`;
  };
  let result = await capture('preflight-desktop');
  await page.setViewportSize({ width: 375, height: 812 });
  result += await capture('preflight-mobile');
  await writeFile('test-results/preflight.txt', result, 'utf8');
} finally {
  await browser.close();
}
