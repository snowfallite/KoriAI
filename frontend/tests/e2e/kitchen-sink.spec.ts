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

	await expect(page.getByRole('region', { name: 'Примитивы' })).toBeVisible();
	for (const name of COMPONENTS) {
		await expect(page.getByRole('region', { name, exact: true })).toBeVisible();
	}
	// Every ChartKind draws on a canvas (S1-06 AC 2); ECharts may add layers, so count charts.
	const charts = page.getByRole('region', { name: 'ChartView' }).locator('[role="img"]');
	await expect(charts).toHaveCount(9);
	await expect(charts.filter({ has: page.locator('canvas') })).toHaveCount(9);
	// The XSS vectors of the Markdown demo stay text (S1-06 AC 3).
	const markdown = page.getByRole('region', { name: 'Markdown', exact: true });
	await expect(markdown.locator('img, script')).toHaveCount(0);
	await expect(markdown).toContainText('<script>');
	expect(await page.evaluate(() => 'hacked' in window)).toBe(false);

	// Night is the Kïoku default; the day theme is one click away.
	const html = page.locator('html');
	await expect(html).toHaveClass(DARK);
	await page.getByRole('button', { name: 'Светлая тема' }).first().click();
	await expect(html).not.toHaveClass(DARK);
	await expect(charts.filter({ has: page.locator('canvas') })).toHaveCount(9);
	await page.getByRole('button', { name: 'Тёмная тема' }).first().click();
	await expect(html).toHaveClass(DARK);

	expect(errors).toEqual([]);
});
