import { expect, test, type Page } from '@playwright/test';

// The CI stack seeds the demo with the broker of the fake: acc1 holds 19 positions, acc2 holds 10
// (backend/fixtures/seed/tinvest/portfolios). The owner has no broker.
const PASSWORD = 'dev-password-123';

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

test('the demo sees the totals, the structure and the positions of each account', async ({
	page
}) => {
	const errors = collectErrors(page);
	await signIn(page, 'demo@example.test');

	await page.getByRole('link', { name: 'Портфель' }).click();
	await expect(page).toHaveURL('/portfolio');

	const rows = page.getByRole('region', { name: 'Позиции' }).getByRole('row');
	await expect(rows).toHaveCount(1 + 29);
	await expect(page.getByRole('img', { name: 'Структура портфеля' })).toBeVisible();
	const totals = page.getByRole('region', { name: 'Итоги' });
	await expect(totals).toContainText('Все счета');
	await expect(totals).toContainText(/4\s440\s856,50/);
	// The yuan bond has no logo: its initials stand in (S1-11 AC 5).
	await expect(rows.filter({ hasText: 'RU000A108TS3' }).getByText('НБ')).toBeVisible();
	const logo = await page.request.get('/api/media/logos/sber');
	expect(logo.headers()['content-type']).toBe('image/png');

	await page.getByLabel('Счёт').click();
	await page.getByRole('option', { name: 'acc2 · ИИС' }).click();
	await expect(page).toHaveURL('/portfolio?account=acc2');
	await expect(rows).toHaveCount(1 + 10);
	await expect(totals).toContainText('acc2 · ИИС');

	expect(errors).toEqual([]);
});

test('the owner without a broker gets the way to the settings', async ({ page }) => {
	const errors = collectErrors(page);
	await signIn(page, 'owner@example.test');

	await page.getByRole('link', { name: 'Портфель' }).click();

	await expect(page.getByText('Брокер не подключён')).toBeVisible();
	await page.getByRole('link', { name: /Открыть Настройки/ }).click();
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

	await page.getByRole('link', { name: 'Портфель' }).click();

	await expect(page.getByRole('alert')).toContainText('Т-Инвестиции не отвечают');
	await page.getByRole('button', { name: 'Повторить' }).click();
	await expect(page.getByRole('img', { name: 'Структура портфеля' })).toBeVisible();
	await expect(page.getByRole('alert')).toHaveCount(0);
});
