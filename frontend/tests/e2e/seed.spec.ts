import { expect, test, type Page } from '@playwright/test';
import type { components } from '../../src/lib/api/schema';

// The CI stack runs cli seed after its migrations (S1-10): the seed users sign in with the public
// password of dev and ci (tech.md §15.2), and the demo has the broker of the fake.
const PASSWORD = 'dev-password-123';

async function signIn(page: Page, email: string) {
	await page.goto('/login');
	await page.getByLabel('Email').fill(email);
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Войти' }).click();
	await expect(page).toHaveURL('/chat');
	await expect(page.getByText(email)).toBeVisible();
}

test('the seed owner signs in', async ({ page }) => {
	await signIn(page, 'owner@example.test');
});

test('the seed demo signs in and has a broker with two accounts', async ({ page }) => {
	await signIn(page, 'demo@example.test');

	// The request shares the session cookie of the page.
	const reply = await page.request.get('/api/auth/me');
	expect(reply.ok()).toBe(true);
	const me = (await reply.json()) as components['schemas']['MeOut'];
	expect(me.broker.connected).toBe(true);
	expect(me.broker.accounts.map((account) => account.alias)).toEqual(['acc1', 'acc2']);
});
