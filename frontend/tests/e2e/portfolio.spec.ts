import { expect, test, type Page } from '@playwright/test';

// The CI stack seeds the demo with the broker of the fake: «Брокерский счёт» (acc1) holds 19
// positions, «ИИС» (acc2) holds 10 (backend/fixtures/seed/tinvest/portfolios). The owner has no
// broker.
const PASSWORD = 'dev-password-123';
const FIRST_LOAD_MS = 15_000;

async function signIn(page: Page, email: string) {
	await page.goto('/login');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Войти' }).click();
	// Until F-03 builds the chat, a new session opens the portfolio (S1-15).
	await expect(page).toHaveURL('/portfolio');
}

function collectErrors(page: Page) {
	const errors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('pageerror', (error) => errors.push(error.message));
	return errors;
}

/** The question a link leaves in the chat (tech.md §13.3: /chat?q= fills, never sends). */
async function questionOf(link: ReturnType<Page['getByRole']>) {
	const href = await link.getAttribute('href');
	const url = new URL(href ?? '', 'http://kori.test');
	expect(url.pathname).toBe('/chat');
	return url.searchParams.get('q');
}

// tech.md S1-15 AC 6 and docs/ui-references/kori-v4/screens/portfolio.png.
test('the demo sees the totals, the structure and the positions of each account', async ({
	page
}) => {
	const errors = collectErrors(page);
	await signIn(page, 'demo@example.test');

	const positions = page.getByRole('region', { name: 'Позиции' });
	const rows = positions.getByRole('row');
	// The first load fills the instrument table: a busy runner may take longer than 5 s.
	await expect(rows).toHaveCount(1 + 29, { timeout: FIRST_LOAD_MS });
	await expect(
		page.getByText(/^Цены Т-Инвестиций на \d\d\.\d\d\.\d{4}, \d\d:\d\d МСК$/)
	).toBeVisible();
	await expect(page.getByRole('img', { name: 'Структура портфеля' })).toBeVisible();

	// The total in whole rubles, the result to the purchase price and the coverage on their own
	// lines; the counter by the heading stays out of its name.
	const totals = page.getByRole('region', { name: 'Итоги' });
	await expect(totals).toContainText(/4\s440\s857/);
	await expect(totals.getByText('к средней цене покупки')).toBeVisible();
	await expect(totals.getByText('29 позиций на 2 счетах', { exact: true })).toBeVisible();
	await expect(positions.getByRole('heading', { name: 'Позиции', exact: true })).toBeVisible();

	// Accounts go by name: the alias stays in the URL and the context of the model.
	const sber = rows.filter({ hasText: 'SBER' });
	await expect(sber).toContainText('Брокерский счёт');
	expect(await page.locator('main').innerText()).not.toMatch(/\bacc\d+\b/);

	// The portfolio and each position lead to the chat; Спросить shows in every row at rest.
	const ask = page.getByRole('link', { name: 'Спросить о портфеле' });
	expect(await questionOf(ask)).toBe('Что с моим портфелем и почему?');
	const askSber = sber.getByRole('link', { name: /Спросить/ });
	await expect(askSber).toHaveCSS('opacity', '1');
	await expect(askSber).toHaveText('Спросить');
	expect(await questionOf(askSber)).toContain('«Сбербанк»');
	await expect(positions).not.toContainText('Наведите');

	// Up to four accounts are tabs; the white one is chosen (tech.md §13.2).
	const accounts = page.getByRole('group', { name: 'Счёт' });
	await expect(accounts.getByRole('radio', { name: 'Все счета' })).toBeChecked();
	await accounts.getByRole('radio', { name: 'ИИС', exact: true }).click();
	await expect(page).toHaveURL('/portfolio?account=acc2');
	await expect(rows).toHaveCount(1 + 10);
	await expect(totals.getByText('10 позиций на счёте «ИИС»', { exact: true })).toBeVisible();

	expect(errors).toEqual([]);
});

// S1-15 AC 6: without a logo an OFZ tile reads «ОФЗ», a currency its code, the rest initials.
test('the tiles without a logo name OFZ and currencies', async ({ page }) => {
	await page.route('**/api/media/logos/**', (route) => route.abort());
	await signIn(page, 'demo@example.test');
	const rows = page.getByRole('region', { name: 'Позиции' }).getByRole('row');
	await expect(rows).toHaveCount(1 + 29, { timeout: FIRST_LOAD_MS });

	const tile = (ticker: string) =>
		rows.filter({ hasText: ticker }).locator('[data-slot="avatar-fallback"]');
	await expect(tile('SU26238RMFS4')).toHaveText('ОФЗ');
	await expect(tile('USD000UTSTOM')).toHaveText('USD');
	await expect(tile('CNYRUB_TOM')).toHaveText('CNY');
	await expect(tile('SBER')).toHaveText('СБ');
	// The yuan bond keeps the initials of its two words (S1-11 AC 5).
	await expect(tile('RU000A108TS3')).toHaveText('НБ');
	const logo = await page.request.get('/api/media/logos/sber');
	expect(logo.headers()['content-type']).toBe('image/png');
});

test('the owner without a broker learns where the connection will be', async ({ page }) => {
	const errors = collectErrors(page);
	await signIn(page, 'owner@example.test');

	await expect(page.getByText('Т-Инвестиции не подключены')).toBeVisible();
	// Until F-01 the settings hold no token form, so the tab offers no button there.
	await expect(page.locator('main').getByRole('link')).toHaveCount(0);
	// No broker, no request: the 409 of the API never reaches the console.
	expect(errors).toEqual([]);
});

test('a failed load shows the reason and Повторить loads the portfolio', async ({ page }) => {
	let failures = 1;
	await page.route('**/api/portfolio', async (route) => {
		if (failures-- > 0) {
			await route.fulfill({
				status: 503,
				contentType: 'application/json',
				body: JSON.stringify({
					code: 'tinvest_unavailable',
					message: 'Т-Инвестиции не отвечают, попробуйте позже',
					details: null,
					request_id: 'e2e'
				})
			});
		} else {
			await route.fallback();
		}
	});
	await signIn(page, 'demo@example.test');

	const alert = page.getByRole('alert');
	await expect(alert).toContainText('Т-Инвестиции не отвечают');
	await expect(alert).toContainText('Код запроса e2e');
	await expect(alert).not.toContainText('×');
	await page.getByRole('button', { name: 'Повторить' }).click();
	await expect(page.getByRole('img', { name: 'Структура портфеля' })).toBeVisible({
		timeout: FIRST_LOAD_MS
	});
	await expect(page.getByRole('alert')).toHaveCount(0);
});
