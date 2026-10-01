import { expect, test, type Page } from '@playwright/test';

// The CI stack registers without invites (docker-compose.ci.yml); the API contract covers them.
const PASSWORD = 'correct-horse-1';
const TABS = [
	['Чат', '/chat'],
	['История', '/history'],
	['Портфель', '/portfolio'],
	['Настройки', '/settings']
] as const;

function newEmail() {
	return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.test`;
}

function collectErrors(page: Page) {
	const errors: string[] = [];
	page.on('console', (message) => {
		// The guard asks /api/auth/me without a session on purpose: that 401 is no error.
		if (message.type() === 'error' && !message.text().includes('status of 401')) {
			errors.push(message.text());
		}
	});
	page.on('pageerror', (error) => errors.push(error.message));
	return errors;
}

async function signIn(page: Page, email: string, password = PASSWORD) {
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Пароль').fill(password);
	await page.getByRole('button', { name: 'Войти' }).click();
}

test('a visitor signs up, signs out, signs in, walks the tabs and signs out', async ({ page }) => {
	const errors = collectErrors(page);
	const email = newEmail();

	// Without a session the SPA leads to /login (S1-05 AC 2).
	await page.goto('/portfolio');
	await expect(page).toHaveURL('/login');

	await page.getByRole('link', { name: 'Регистрация' }).click();
	await expect(page).toHaveURL('/register');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Имя').fill('Тест');
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Зарегистрироваться' }).click();
	await expect(page).toHaveURL('/chat');
	await expect(page.getByText(email)).toBeVisible();

	await page.getByRole('button', { name: 'Выйти' }).click();
	await expect(page).toHaveURL('/login');

	await signIn(page, email);
	await expect(page).toHaveURL('/chat');

	// The tabs come from NAV in its order (S1-05 AC 7).
	const tabs = page.getByRole('link', { name: /^(Чат|История|Портфель|Настройки)$/ });
	await expect(tabs).toHaveText(TABS.map(([label]) => label));
	for (const [label, path] of TABS) {
		await page.getByRole('link', { name: label }).click();
		await expect(page).toHaveURL(path);
		await expect(page.getByRole('heading', { level: 1, name: label })).toBeVisible();
		await expect(page.getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page');
	}

	await page.getByRole('button', { name: 'Выйти' }).click();
	await expect(page).toHaveURL('/login');
	await page.goto('/settings');
	await expect(page).toHaveURL('/login');

	// The CSP of the shell lets the whole flow run (S1-05 AC 6).
	expect(errors).toEqual([]);
});

test('a wrong password keeps the visitor on the login page with the reason', async ({ page }) => {
	await page.goto('/register?invite=from-the-link');
	await expect(page.getByLabel('Код приглашения')).toHaveValue('from-the-link');

	await page.goto('/login');
	await signIn(page, newEmail(), 'wrong-password-1');

	await expect(page.getByRole('alert')).toHaveText('Неверный email или пароль');
	await expect(page).toHaveURL('/login');
});

test('the SPA shell carries the content security policy', async ({ request }) => {
	const html = await (await request.get('/login')).text();

	const policy = /<meta http-equiv="content-security-policy" content="([^"]+)"/.exec(html)?.[1];
	expect(policy?.split('; ').sort()).toEqual([
		"connect-src 'self'",
		"default-src 'self'",
		"img-src 'self' data:",
		expect.stringMatching(/^script-src 'self' 'sha256-[\w+/=]+'$/),
		"style-src 'self' 'unsafe-inline'"
	]);
});
