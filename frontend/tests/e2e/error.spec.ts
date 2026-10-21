import { expect, test, type Page } from '@playwright/test';

// tech.md S1-15 AC 8: a failed start of the app and an unknown address show the page of
// docs/ui-references/kori-v4/screens/error.png instead of «500 Internal Error» and «404 Not Found».

async function signUp(page: Page, baseURL: string | undefined) {
	const email = `error-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.test`;
	const reply = await page.request.post('/api/auth/register', {
		headers: { Origin: baseURL ?? '' },
		data: { email, password: 'correct-horse-1', invite_code: null, display_name: null }
	});
	expect(reply.status()).toBe(201);
}

async function expectNoStockText(page: Page) {
	const text = await page.locator('body').innerText();
	for (const stock of ['Internal Error', 'Not Found', '404', '500']) {
		expect(text).not.toContain(stock);
	}
}

test('an unknown address says so and leads to the portfolio', async ({ page }) => {
	await page.goto('/no-such-page');

	await expect(page.getByRole('heading', { level: 1, name: 'Страница не найдена' })).toBeVisible();
	await expect(page.getByText('По адресу /no-such-page ничего нет.')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Kōri' })).toBeVisible();
	await expectNoStockText(page);

	// Without a session the portfolio sends the visitor to sign in first.
	await page.getByRole('link', { name: 'Открыть портфель' }).click();
	await expect(page).toHaveURL('/login');
});

test('a failed start gives the reason, the request code and Повторить', async ({
	page,
	baseURL
}) => {
	await signUp(page, baseURL);
	let failures = 1;
	await page.route('**/api/auth/me', async (route) => {
		if (failures-- > 0) {
			await route.fulfill({
				status: 503,
				contentType: 'application/json',
				body: JSON.stringify({
					code: 'internal',
					message: 'Сервер недоступен, попробуйте позже',
					details: null,
					request_id: 'e2e-start'
				})
			});
		} else {
			await route.fallback();
		}
	});

	await page.goto('/portfolio');

	await expect(
		page.getByRole('heading', { level: 1, name: 'Сервер недоступен, попробуйте позже' })
	).toBeVisible();
	await expect(page.getByText('Код запроса e2e-start')).toBeVisible();
	await expectNoStockText(page);
	await page.getByRole('button', { name: 'Повторить' }).click();
	await expect(page.getByRole('heading', { level: 1, name: 'Портфель' })).toBeVisible();
	await expect(page).toHaveURL('/portfolio');
});

test('a lost network reads «Нет связи с сервером»', async ({ page, baseURL }) => {
	await signUp(page, baseURL);
	await page.route('**/api/auth/me', (route) => route.abort('internetdisconnected'));

	await page.goto('/portfolio');

	await expect(page.getByRole('heading', { level: 1, name: 'Нет связи с сервером' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Повторить' })).toBeVisible();
	await expectNoStockText(page);
});
