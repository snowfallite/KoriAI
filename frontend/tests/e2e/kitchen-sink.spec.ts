import { expect, test } from '@playwright/test';

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
// The sheets of the v3 mockup the page repeats (S1-14 AC 7).
const SHEETS = ['Кнопки', 'Выбранное', 'Карточки', 'Уведомления'];

const DARK = /(^|\s)dark(\s|$)/;

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

	// Night is the Kïoku default; the day theme is one click away (S1-14 AC 7).
	await expect(html).toHaveClass(DARK);
	for (const day of [false, true]) {
		if (day) {
			await theme.getByRole('radio', { name: 'День' }).click();
			await expect(html).not.toHaveClass(DARK);
		}
		await expect(page.getByRole('region', { name: 'Примитивы' })).toBeVisible();
		for (const name of [...SHEETS, ...COMPONENTS]) {
			await expect(page.getByRole('region', { name, exact: true })).toBeVisible();
		}
		await expect(charts).toHaveCount(9);
		await expect(canvases).toHaveCount(8);
	}
	await theme.getByRole('radio', { name: 'Ночь' }).click();
	await expect(html).toHaveClass(DARK);

	// The XSS vectors of the Markdown demo stay text (S1-06 AC 3).
	const markdown = page.getByRole('region', { name: 'Markdown', exact: true });
	await expect(markdown.locator('img, script')).toHaveCount(0);
	await expect(markdown).toContainText('<script>');
	expect(await page.evaluate(() => 'hacked' in window)).toBe(false);

	// The dialog is a white panel with a black title strip and two actions (tech.md §13.2).
	const confirm = page.getByRole('region', { name: 'ConfirmDialog', exact: true });
	await confirm.getByRole('button', { name: 'Удалить тред' }).click();
	const dialog = page.getByRole('alertdialog', { name: 'Удалить тред?' });
	await expect(dialog).toBeVisible();
	await dialog.getByRole('button', { name: 'Отмена' }).click();
	await expect(dialog).toBeHidden();

	expect(errors).toEqual([]);
});

// S1-08 AC 1: the button opens an echo stream; its dev.echo frame carries the payload back.
test('Эхо streams its payload back over SSE', async ({ page }) => {
	await page.goto('/dev/kitchen-sink');
	const sse = page.getByRole('region', { name: 'SSE', exact: true });

	await sse.getByRole('button', { name: 'Эхо' }).click();

	await expect(sse.getByLabel('Ответ эха')).toContainText('Привет, Kōri');
	await expect(sse).toContainText('статус done · seq 2');
});
