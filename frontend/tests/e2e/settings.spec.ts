import { expect, test, type Page } from '@playwright/test';

// F-01 on the CI stack: registration takes no invite, and the T-Invest fake lists the two
// read-only accounts of the seed for any token, «Брокерский счёт» and «ИИС»
// (backend/fixtures/seed/tinvest/accounts.yaml). Each test signs up its own user.
const PASSWORD = 'correct-horse-1';
const TOKEN = 't.e2e-read-only-token-Fx7k';
const HINT = 'Нужен токен с доступом «Только чтение». Заявки и переводы сервис не делает.';
const STORE = 'Храним токен зашифрованным и показываем только последние 4 символа.';

function collectErrors(page: Page) {
	const errors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('pageerror', (error) => errors.push(error.message));
	return errors;
}

async function signUp(page: Page) {
	const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
	await page.goto('/register');
	await page.getByLabel('Email').fill(`e2e-${suffix}@example.test`);
	await page.getByLabel('Имя').fill('Тест');
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Создать аккаунт' }).click();
	await expect(page).toHaveURL('/portfolio');
}

test('a user connects a token, hides an account and disconnects', async ({ page }) => {
	const errors = collectErrors(page);
	await signUp(page);

	// Without a broker the portfolio leads to the settings (S1-11 AC 3).
	await expect(page.getByText('Т-Инвестиции не подключены')).toBeVisible();
	await page.getByRole('link', { name: 'Открыть настройки' }).click();
	await expect(page).toHaveURL('/settings');

	// AC 9: the facts about the token stand under its field.
	const field = page.getByLabel('Токен Т-Инвестиций');
	await expect(field).toHaveAttribute('type', 'password');
	await expect(page.getByText(HINT)).toBeVisible();
	await expect(page.getByText(STORE)).toBeVisible();
	const help = page.getByRole('link', { name: 'Как выпустить токен' });
	await expect(help).toHaveAttribute('href', 'https://developer.tbank.ru/invest/intro/intro/token');
	await expect(help).toHaveAttribute('target', '_blank');

	await field.fill(` ${TOKEN}\n`);
	await page.getByRole('button', { name: 'Подключить' }).click();

	await expect(page.getByText('Т-Инвестиции подключены, найдено 2 счёта')).toBeVisible();
	const broker = page.getByRole('region', { name: 'Брокер' });
	await expect(broker.getByText('Подключён', { exact: true })).toBeVisible();
	await expect(broker).toContainText(`…${TOKEN.slice(-4)}`);
	const rows = broker.getByRole('row');
	await expect(rows).toHaveCount(1 + 2);
	await expect(rows.nth(1)).toContainText('Брокерский счёт');
	await expect(rows.nth(2)).toContainText('ИИС');
	// AC 9: no other place repeats the facts; accounts go by name, never by alias.
	await expect(page.getByText(HINT)).toHaveCount(0);
	await expect(page.getByText(STORE)).toHaveCount(0);
	expect(await page.locator('main').innerText()).not.toMatch(/\bacc\d+\b/);

	// AC 8: a hidden account stays hidden.
	const iis = page.getByRole('switch', { name: 'Показывать «ИИС»' });
	await expect(iis).toBeChecked();
	await iis.click();
	await expect(iis).not.toBeChecked();
	await page.reload();
	await expect(page.getByRole('switch', { name: 'Показывать «ИИС»' })).not.toBeChecked();
	await expect(page.getByRole('switch', { name: 'Показывать «Брокерский счёт»' })).toBeChecked();

	// AC 5: the check keeps a working token.
	await page.getByRole('button', { name: 'Проверить токен' }).click();
	await expect(page.getByText('Токен работает')).toBeVisible();

	// AC 6: the dialog drops the token and the accounts; the field comes back.
	await page.getByRole('button', { name: 'Отключить' }).click();
	const dialog = page.getByRole('alertdialog');
	await expect(dialog).toContainText('Отключить Т-Инвестиции?');
	await dialog.getByRole('button', { name: 'Отключить' }).click();
	await expect(page.getByLabel('Токен Т-Инвестиций')).toBeVisible();
	await expect(page.getByRole('row')).toHaveCount(0);
	await page.getByRole('link', { name: 'Портфель', exact: true }).click();
	await expect(page.getByText('Т-Инвестиции не подключены')).toBeVisible();

	expect(errors).toEqual([]);
});

test('a token that does more than read gets the reason at its field', async ({ page }) => {
	const reason = 'Токен даёт не только чтение: нужен доступ «Только чтение»';
	await page.route('**/api/broker/connection', async (route) => {
		if (route.request().method() !== 'PUT') return route.fallback();
		await route.fulfill({
			status: 422,
			contentType: 'application/json',
			body: JSON.stringify({
				code: 'token_not_read_only',
				message: reason,
				details: null,
				request_id: 'e2e'
			})
		});
	});
	await signUp(page);
	await page.goto('/settings');

	const field = page.getByLabel('Токен Т-Инвестиций');
	await field.fill(TOKEN);
	await page.getByRole('button', { name: 'Подключить' }).click();

	await expect(page.getByText(reason)).toBeVisible();
	await expect(field).toHaveAttribute('aria-invalid', 'true');
	await expect(page.getByText(/Т-Инвестиции подключены/)).toHaveCount(0);
	await expect(page.getByRole('row')).toHaveCount(0);
});
