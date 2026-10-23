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
// tech.md S1-15 AC 1: the captions that made statements instead of informing are gone.
const SLOGANS = [
	'Вход для закрытого круга',
	'Т-Инвестиции · доступ только на чтение',
	'Токен хранится зашифрованным',
	'Пароль от 10 символов · хранится как хеш',
	'Email и пароль'
];

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

/** The tags the page sets in caps: S1-15 AC 3 leaves them to the column heads of tables. */
function uppercased(page: Page) {
	return page.evaluate(() =>
		[...document.querySelectorAll('body *')]
			.filter((el) => getComputedStyle(el).textTransform === 'uppercase')
			.map((el) => el.tagName.toLowerCase())
	);
}

test('a visitor signs up, signs out, signs in, walks the tabs and signs out', async ({ page }) => {
	const errors = collectErrors(page);
	const email = newEmail();

	// Without a session the SPA leads to /login (S1-05 AC 2).
	await page.goto('/portfolio');
	await expect(page).toHaveURL('/login');

	await page.getByRole('link', { name: 'Регистрация по приглашению' }).click();
	await expect(page).toHaveURL('/register');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Имя').fill('Тест');
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Создать аккаунт' }).click();
	// A new session opens the chat (F-03).
	await expect(page).toHaveURL('/chat');
	await expect(page.getByText(email)).toBeVisible();

	await page.getByRole('button', { name: 'Выйти' }).click();
	await expect(page).toHaveURL('/login');

	await signIn(page, email);
	await expect(page).toHaveURL('/chat');

	// The tabs come from NAV in its order (S1-05 AC 7); the name «Kōri» heads the app (S1-15 AC 1).
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
	expect(await uppercased(page)).toEqual([]);

	// Dark is the default; the segments of the sidebar switch the theme (tech.md §13.2).
	const html = page.locator('html');
	const theme = page.getByRole('group', { name: 'Тема' });
	await expect(html).toHaveClass(DARK);
	await expect(theme.getByRole('radio', { name: 'Тёмная' })).toBeChecked();
	await theme.getByRole('radio', { name: 'Светлая' }).click();
	await expect(html).not.toHaveClass(DARK);
	await theme.getByRole('radio', { name: 'Тёмная' }).click();
	await expect(html).toHaveClass(DARK);

	await page.getByRole('button', { name: 'Выйти' }).click();
	await expect(page).toHaveURL('/login');
	await page.goto('/settings');
	await expect(page).toHaveURL('/login');

	// The CSP of the shell lets the whole flow run (S1-05 AC 6).
	expect(errors).toEqual([]);
});

// S1-15 AC 1, 3, 5, 9: the scene «свет над графиком», the spaced name, one action, no slogans.
test('the login page shows the name, one action and the way to register', async ({ page }) => {
	const errors = collectErrors(page);
	await page.goto('/login');

	await expect(page.getByRole('img', { name: 'Kōri' })).toBeVisible();
	await expect(page.getByRole('heading', { level: 1, name: 'Вход' })).toBeVisible();
	const text = await page.locator('body').innerText();
	expect(text).not.toContain('氷');
	for (const slogan of SLOGANS) expect(text).not.toContain(slogan);
	// One action: Войти; Показать lives inside the password field.
	await expect(page.getByRole('button')).toHaveCount(2);
	await expect(page.getByRole('button', { name: 'Войти' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Показать' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Регистрация по приглашению' })).toBeVisible();
	await expect(page.getByRole('group', { name: 'Тема' })).toHaveCount(0);
	expect(await uppercased(page)).toEqual([]);

	// The password shows on demand from inside its field.
	await page.getByLabel('Пароль').fill('secret-123');
	await page.getByRole('button', { name: 'Показать' }).click();
	await expect(page.getByLabel('Пароль')).toHaveAttribute('type', 'text');
	await page.getByRole('button', { name: 'Скрыть' }).click();
	await expect(page.getByLabel('Пароль')).toHaveAttribute('type', 'password');

	expect(errors).toEqual([]);
});

// S1-15 AC 9: keyboard focus shows on every control: a field a 2 px line under it, the rest the
// ring of the brand.
test('keyboard focus shows on every control of the login page', async ({ page }) => {
	await page.goto('/login');
	// The SPA draws the form once its script runs: tab only after that.
	await expect(page.getByLabel('Email')).toBeVisible();

	for (const field of [page.getByLabel('Email'), page.getByLabel('Пароль')]) {
		await page.keyboard.press('Tab');
		await expect(field).toBeFocused();
		await expect(field).toHaveCSS('box-shadow', /inset/);
	}
	for (const control of [
		page.getByRole('button', { name: 'Показать' }),
		page.getByRole('button', { name: 'Войти' }),
		page.getByRole('link', { name: 'Регистрация по приглашению' })
	]) {
		await page.keyboard.press('Tab');
		await expect(control).toBeFocused();
		await expect(control).toHaveCSS('outline-style', 'solid');
		await expect(control).toHaveCSS('outline-width', '2px');
	}
});

// S1-15 AC 5: an error lies at its field as a red line and a sentence, without a ×.
test('a wrong password keeps the visitor on the login page with the reason at the field', async ({
	page
}) => {
	await page.goto('/register?invite=from-the-link');
	await expect(page.getByLabel('Код приглашения')).toHaveValue('from-the-link');

	await page.goto('/login');
	await signIn(page, newEmail(), 'wrong-password-1');

	const alert = page.getByRole('alert');
	await expect(alert).toContainText('Неверный email или пароль');
	await expect(alert).not.toContainText('×');
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
	await expect(page.getByLabel('Пароль')).toHaveAccessibleDescription('Не короче 10 символов');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Создать аккаунт' }).click();

	const field = page.getByLabel('Email');
	await expect(field).toHaveAttribute('aria-invalid', 'true');
	await expect(field).toHaveAccessibleDescription('Этот email уже зарегистрирован. Войти');
	await expect(page).toHaveURL('/register');
	await page.locator('#email-error').getByRole('link', { name: 'Войти' }).click();
	await expect(page).toHaveURL('/login');
});

test.describe('on a phone', () => {
	test.use({ viewport: { width: 390, height: 844 } });

	// docs/ui-references/kori-v4 (phone-login.png): the name on top, the form at the bottom.
	test('the login page fits the phone without a sideways scroll', async ({ page }) => {
		await page.goto('/login');
		const name = await page.getByRole('img', { name: 'Kōri' }).boundingBox();
		const form = await page.getByRole('form', { name: 'Вход' }).boundingBox();

		expect(name && form && name.y + name.height <= form.y).toBe(true);
		expect(form && Math.round(form.y + form.height)).toBe(844 - 12);
		expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
	});
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
