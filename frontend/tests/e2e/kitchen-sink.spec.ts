import { expect, test, type Page } from '@playwright/test';

// Every composite of tech.md §13.2: the kitchen-sink gives each its own region.
const COMPONENTS = [
	'AppShell',
	'PageHeader',
	'EmptyState',
	'ErrorState',
	'LoadingBlock',
	'DataTable',
	'ChartView',
	'ArtifactTable',
	'ArtifactImage',
	'ArtifactView',
	'Markdown',
	'SourceList',
	'StatCard',
	'MoneyText',
	'PercentText',
	'InstrumentLogo',
	'InstrumentBadge',
	'AccountSelect',
	'PeriodSelect',
	'UsageMeter',
	'ConfirmDialog',
	'CopyButton',
	'ThemeToggle',
	'Disclaimer',
	'Logo'
];
// The sheets of the system page of v4 the kitchen-sink repeats (S1-15).
const SHEETS = ['Глифы', 'Кнопки', 'Шрифты', 'Выбранное', 'Карточки', 'Уведомления', 'Данные'];

const DARK = /(^|\s)dark(\s|$)/;

/** Elements in caps that are not table column heads (or inside one). */
function uppercasedOutsideHeads(page: Page) {
	return page.evaluate(() =>
		[...document.querySelectorAll('body *')]
			.filter((el) => getComputedStyle(el).textTransform === 'uppercase' && !el.closest('th'))
			.map((el) => `${el.tagName.toLowerCase()}: ${el.textContent?.slice(0, 40)}`)
	);
}

// The page lives behind the (app) guard: sign up first. page.request shares the cookies of the
// page, and the API takes a mutation only with our Origin (tech.md §3.5).
test.beforeEach(async ({ page, baseURL }) => {
	const email = `kitchen-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.test`;
	const reply = await page.request.post('/api/auth/register', {
		headers: { Origin: baseURL ?? '' },
		data: { email, password: 'correct-horse-1', invite_code: null, display_name: null }
	});
	expect(reply.status()).toBe(201);
});

test('kitchen-sink shows every component in both themes without console errors', async ({
	page
}) => {
	const errors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('pageerror', (error) => errors.push(error.message));

	await page.goto('/dev/kitchen-sink');

	const html = page.locator('html');
	const theme = page.getByRole('group', { name: 'Тема' }).first();
	// Every ChartKind draws (S1-06 AC 2): a pie as plates, the other eight on a canvas.
	const charts = page.getByRole('region', { name: 'ChartView' }).locator('[role="img"]');
	const canvases = charts.filter({ has: page.locator('canvas') });

	// Dark is the Kïoku default; the light theme is one click away (S1-15).
	await expect(html).toHaveClass(DARK);
	for (const light of [false, true]) {
		if (light) {
			await theme.getByRole('radio', { name: 'Светлая' }).click();
			await expect(html).not.toHaveClass(DARK);
		}
		await expect(page.getByRole('region', { name: 'Примитивы' })).toBeVisible();
		for (const name of [...SHEETS, ...COMPONENTS]) {
			await expect(page.getByRole('region', { name, exact: true })).toBeVisible();
		}
		await expect(charts).toHaveCount(9);
		await expect(canvases).toHaveCount(8);
		// S1-15 AC 3: caps live in the column heads of tables only.
		expect(await uppercasedOutsideHeads(page)).toEqual([]);
	}
	await theme.getByRole('radio', { name: 'Тёмная' }).click();
	await expect(html).toHaveClass(DARK);

	// S1-15 AC 1: no seal 氷 anywhere; AC 7: notices and toasts carry no glyph cells.
	expect(await page.locator('body').innerText()).not.toContain('氷');
	await expect(page.getByRole('region', { name: 'Уведомления', exact: true })).not.toContainText(
		/[×→↓]/
	);

	// The XSS vectors of the Markdown demo stay text (S1-06 AC 3).
	const markdown = page.getByRole('region', { name: 'Markdown', exact: true });
	await expect(markdown.locator('img, script')).toHaveCount(0);
	await expect(markdown).toContainText('<script>');
	expect(await page.evaluate(() => 'hacked' in window)).toBe(false);

	// The dialog is a white panel with a black title strip and two actions; its only × stands at
	// Удалить (tech.md §13.2, S1-15 AC 7).
	const confirm = page.getByRole('region', { name: 'ConfirmDialog', exact: true });
	await confirm.getByRole('button', { name: 'Удалить чат' }).click();
	const dialog = page.getByRole('alertdialog', { name: 'Удалить чат?' });
	await expect(dialog).toBeVisible();
	expect((await dialog.innerText()).split('×')).toHaveLength(2);
	await expect(dialog.getByRole('button', { name: 'Закрыть' })).toHaveCount(0);
	await dialog.getByRole('button', { name: 'Отмена' }).click();
	await expect(dialog).toBeHidden();

	expect(errors).toEqual([]);
});

/** Animations of the page that still run. */
function running(page: Page) {
	return page.evaluate(
		() => document.getAnimations().filter((animation) => animation.playState === 'running').length
	);
}

// S1-15 AC 10: who asks for less motion gets none; the skeletons of the page pulse otherwise.
test('reduced motion stops every animation', async ({ page }) => {
	await page.goto('/dev/kitchen-sink');
	await expect(page.getByRole('region', { name: 'LoadingBlock' })).toBeVisible();
	await expect.poll(() => running(page)).toBeGreaterThan(0);

	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.reload();
	await expect(page.getByRole('region', { name: 'LoadingBlock' })).toBeVisible();
	await expect.poll(() => running(page)).toBe(0);
});

// S1-08 AC 1: the button opens an echo stream; its dev.echo frame carries the payload back.
test('Эхо streams its payload back over SSE', async ({ page }) => {
	await page.goto('/dev/kitchen-sink');
	const sse = page.getByRole('region', { name: 'SSE', exact: true });

	await sse.getByRole('button', { name: 'Эхо' }).click();

	await expect(sse.getByLabel('Ответ эха')).toContainText('Привет, Kōri');
	await expect(sse).toContainText('статус done · seq 2');
});
