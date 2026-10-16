import { expect, test, type Page } from '@playwright/test';

// The CI stack registers without invites (docker-compose.ci.yml); the API contract covers them.
const PASSWORD = 'correct-horse-1';
const TABS = [
	['Чат', '/chat'],
	['История', '/history'],
	['Портфель', '/portfolio'],
	['Настройки', '/settings']
] as const;
const DARK = /(^|\s)dark(\s|$)/;

function newEmail() {
	return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.test`;
}

function collectErrors(page: Page) {
	const errors: string[] = [];
	page.on('console', (message) => {
		// The guard asks /api/auth/me without a session on purpose: that 401 is no error, nor are
		// the 401 of a wrong password and the 409 of a taken email the forms show at their fields.
		if (message.type() === 'error' && !/status of (401|409)/.test(message.text())) {
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
	await page.getByRole('button', { name: 'Создать аккаунт' }).click();
	await expect(page).toHaveURL('/chat');
	await expect(page.getByText(email)).toBeVisible();

	await page.getByRole('button', { name: 'Выйти' }).click();
	await expect(page).toHaveURL('/login');

	await signIn(page, email);
	await expect(page).toHaveURL('/chat');

	// The tabs come from NAV in its order (S1-05 AC 7); the seal names the app (S1-14 AC 3).
	await expect(page.getByRole('link', { name: 'Kōri' })).toBeVisible();
	const tabs = page.getByRole('link', { name: /^(Чат|История|Портфель|Настройки)$/ });
	await expect(tabs).toHaveText(TABS.map(([label]) => label));
	for (const [label, path] of TABS) {
		await page.getByRole('link', { name: label, exact: true }).click();
		await expect(page).toHaveURL(path);
		await expect(page.getByRole('heading', { level: 1, name: label })).toBeVisible();
		await expect(page.getByRole('link', { name: label, exact: true })).toHaveAttribute(
			'aria-current',
			'page'
		);
	}

	// Night is the default; the segments of the sidebar switch the theme (tech.md §13.2).
	const html = page.locator('html');
	const theme = page.getByRole('group', { name: 'Тема' });
	await expect(html).toHaveClass(DARK);
	await expect(theme.getByRole('radio', { name: 'Ночь' })).toBeChecked();
	await theme.getByRole('radio', { name: 'День' }).click();
	await expect(html).not.toHaveClass(DARK);
	await theme.getByRole('radio', { name: 'Ночь' }).click();
	await expect(html).toHaveClass(DARK);

	await page.getByRole('button', { name: 'Выйти' }).click();
	await expect(page).toHaveURL('/login');
	await page.goto('/settings');
	await expect(page).toHaveURL('/login');

	// The CSP of the shell lets the whole flow run (S1-05 AC 6).
	expect(errors).toEqual([]);
});

// S1-14 AC 4: an error the API ties to a field shows at that field.
test('a wrong password keeps the visitor on the login page with the reason at the field', async ({
	page
}) => {
	await page.goto('/register?invite=from-the-link');
	await expect(page.getByLabel('Код приглашения')).toHaveValue('from-the-link');

	await page.goto('/login');
	await signIn(page, newEmail(), 'wrong-password-1');

	await expect(page.getByRole('alert')).toContainText('Неверный email или пароль');
	await expect(page.getByLabel('Пароль')).toHaveAttribute('aria-invalid', 'true');
	await expect(page.getByLabel('Пароль')).toHaveAccessibleDescription('Неверный email или пароль');
	await expect(page).toHaveURL('/login');
});

test('a taken email is marked at its field with the way to sign in', async ({ page, baseURL }) => {
	const email = newEmail();
	const reply = await page.request.post('/api/auth/register', {
		headers: { Origin: baseURL ?? '' },
		data: { email, password: PASSWORD, invite_code: null, display_name: null }
	});
	expect(reply.status()).toBe(201);
	await page.context().clearCookies();

	await page.goto('/register');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Создать аккаунт' }).click();

	const field = page.getByLabel('Email');
	await expect(field).toHaveAttribute('aria-invalid', 'true');
	await expect(field).toHaveAccessibleDescription(/Этот email уже зарегистрирован/);
	await expect(page).toHaveURL('/register');
	await page.getByRole('link', { name: 'Войти' }).click();
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
