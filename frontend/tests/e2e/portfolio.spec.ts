import { expect, test, type Page } from '@playwright/test';

// The CI stack seeds the demo with the broker of the fake: acc1 holds 19 positions, acc2 holds 10
// (backend/fixtures/seed/tinvest/portfolios). The owner has no broker.
const PASSWORD = 'dev-password-123';
const FIRST_LOAD_MS = 15_000;

async function signIn(page: Page, email: string) {
	await page.goto('/login');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Войти' }).click();
	await expect(page).toHaveURL('/chat');
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

test('the demo sees the totals, the structure and the positions of each account', async ({
	page
}) => {
	const errors = collectErrors(page);
	await signIn(page, 'demo@example.test');

	await page.getByRole('link', { name: 'Портфель', exact: true }).click();
	await expect(page).toHaveURL('/portfolio');

	const positions = page.getByRole('region', { name: 'Позиции' });
	const rows = positions.getByRole('row');
	// The first load fills the instrument table: a busy runner may take longer than 5 s.
	await expect(rows).toHaveCount(1 + 29, { timeout: FIRST_LOAD_MS });
	await expect(page.getByRole('img', { name: 'Структура портфеля' })).toBeVisible();
	// The hero shows whole rubles; the counter by the heading stays out of its name (S1-14 AC 8).
	const totals = page.getByRole('region', { name: 'Итоги' });
	await expect(totals).toContainText(/4\s440\s857/);
	await expect(totals).toContainText('29 позиций на 2 счетах');
	await expect(positions.getByRole('heading', { name: 'Позиции', exact: true })).toBeVisible();
	// The yuan bond has no logo: its initials stand in (S1-11 AC 5).
	await expect(rows.filter({ hasText: 'RU000A108TS3' }).getByText('НБ')).toBeVisible();
	const logo = await page.request.get('/api/media/logos/sber');
	expect(logo.headers()['content-type']).toBe('image/png');

	// The portfolio and each position lead to the chat with a question (S1-14 AC 5).
	const ask = page.getByRole('link', { name: 'Спросить Kōri о портфеле' });
	expect(await questionOf(ask)).toBe('Что с моим портфелем и почему?');
	const sber = rows.filter({ hasText: 'SBER' }).getByRole('link', { name: /^Спросить/ });
	expect(await questionOf(sber)).toMatch(/^Почему Сбербанк /);

	// Up to four accounts are tabs; the white one is chosen (tech.md §13.2).
	const accounts = page.getByRole('group', { name: 'Счёт' });
	await expect(accounts.getByRole('radio', { name: 'Все счета' })).toBeChecked();
	await accounts.getByRole('radio', { name: 'acc2 · ИИС' }).click();
	await expect(page).toHaveURL('/portfolio?account=acc2');
	await expect(rows).toHaveCount(1 + 10);
	await expect(totals).toContainText('acc2 · ИИС');

	expect(errors).toEqual([]);
});

test('the owner without a broker gets the way to the settings', async ({ page }) => {
	const errors = collectErrors(page);
	await signIn(page, 'owner@example.test');

	await page.getByRole('link', { name: 'Портфель', exact: true }).click();

	await expect(page.getByText('Брокер не подключён')).toBeVisible();
	await page.getByRole('link', { name: 'Подключить токен' }).click();
	await expect(page).toHaveURL('/settings');
	// No broker, no request: the 409 of the API never reaches the console.
	expect(errors).toEqual([]);
});

test('a failed load shows the reason and Повторить loads the portfolio', async ({ page }) => {
	await signIn(page, 'demo@example.test');
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

	await page.getByRole('link', { name: 'Портфель', exact: true }).click();

	await expect(page.getByRole('alert')).toContainText('Т-Инвестиции не отвечают');
	await expect(page.getByRole('alert')).toContainText('e2e');
	await page.getByRole('button', { name: 'Повторить' }).click();
	await expect(page.getByRole('img', { name: 'Структура портфеля' })).toBeVisible({
		timeout: FIRST_LOAD_MS
	});
	await expect(page.getByRole('alert')).toHaveCount(0);
});
