import { expect, test, type Page } from '@playwright/test';

// F-03 on the CI stack: the fake model answers after 3 s (FAKE_FAULTS,
// backend/fixtures/seed/faults/f03_e2e.yaml) with the scenarios of
// backend/fixtures/seed/llm/f03_basic.yaml. The suite sits at the limit of ten registrations a
// minute from one address (tech.md §3.5), so these tests sign in once as the seed owner and go one
// after another in one page: one run at a time is the rule of a user (§3.4).
const OWNER = 'owner@example.test';
const PASSWORD = 'dev-password-123';
const DURATION = 'Что такое дюрация облигации?';
const ANSWER = 'Дюрация показывает, сколько лет в среднем инвестор ждёт возврата';
const RUN_MS = 20_000;

test.describe.configure({ mode: 'serial' });

let page: Page;
const errors: string[] = [];

test.beforeAll(async ({ browser }, info) => {
	page = await browser.newPage({ baseURL: info.project.use.baseURL });
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	page.on('pageerror', (error) => errors.push(error.message));
	await page.goto('/login');
	await page.getByLabel('Email').fill(OWNER);
	await page.getByLabel('Пароль').fill(PASSWORD);
	await page.getByRole('button', { name: 'Войти' }).click();
	// A new session opens the chat (F-03).
	await expect(page).toHaveURL('/chat');
});

test.afterAll(async () => {
	await page.close();
});

test('a question streams its answer and stays in the thread', async () => {
	await expect(page.getByRole('heading', { level: 1, name: 'Новый чат' })).toBeVisible();
	await expect(
		page.getByText(/^(Доброе утро|Добрый день|Добрый вечер|Доброй ночи), Владелец$/)
	).toBeVisible();
	const field = page.getByLabel('Вопрос', { exact: true });
	// Nothing goes while the field is blank (AC 8).
	await field.fill('   ');
	await expect(page.getByRole('button', { name: 'Спросить' })).toBeDisabled();

	await field.fill(DURATION);
	await field.press('Enter');

	await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/);
	const turn = page.getByRole('article', { name: /^Вопрос 1/ });
	await expect(turn).toContainText(DURATION);
	await expect(turn.getByText(ANSWER)).toBeVisible({ timeout: RUN_MS });
	await expect(turn.getByRole('list', { name: 'Как получен ответ' })).toContainText('GigaChat-2');
	await expect(turn.getByRole('button', { name: 'Копировать' })).toBeVisible();
	await expect(turn.getByRole('button', { name: 'Повторить' })).toBeVisible();
	await expect(page.getByText('1 вопрос', { exact: true })).toBeVisible();

	// Shift+Enter breaks the line and sends nothing (AC 8).
	const next = page.getByLabel('Уточнить вопрос');
	await next.fill('Первая строка');
	await next.press('Shift+Enter');
	await next.pressSequentially('вторая');
	await expect(next).toHaveValue('Первая строка\nвторая');
	await expect(page.getByRole('article')).toHaveCount(1);

	// The answer survives a reload: it comes from the thread (AC 3).
	await page.reload();
	await expect(page.getByRole('article', { name: /^Вопрос 1/ }).getByText(ANSWER)).toBeVisible();
	expect(errors).toEqual([]);
});

test('Остановить ends a running answer and keeps it as stopped', async () => {
	await page.goto('/chat');
	const field = page.getByLabel('Вопрос', { exact: true });
	await field.fill(DURATION);
	await page.getByRole('button', { name: 'Спросить' }).click();

	const stop = page.getByRole('button', { name: 'Остановить' });
	await expect(stop).toBeVisible();
	await stop.click();

	const turn = page.getByRole('article', { name: /^Вопрос 1/ });
	await expect(turn.getByText('Ответ остановлен')).toBeVisible({ timeout: RUN_MS });
	await expect(stop).toBeHidden();
	await expect(page.getByRole('button', { name: 'Спросить' })).toBeVisible();
	expect(errors).toEqual([]);
});

test('/chat?q= and a suggestion fill the field and send nothing', async () => {
	const question = 'Как устроен купон облигации?';

	await page.goto(`/chat?q=${encodeURIComponent(question)}`);

	const field = page.getByLabel('Вопрос', { exact: true });
	await expect(field).toHaveValue(question);
	await expect(page).toHaveURL(/\/chat\?q=/);
	await expect(page.getByRole('article')).toHaveCount(0);

	// The fan of a wide column or the list of a narrow one: the hidden one is out of the roles.
	const suggestions = page.getByRole('list', { name: 'Примеры вопросов' });
	await suggestions.getByRole('button', { name: /Дивиденды и купоны до конца года/ }).click();
	await expect(field).toHaveValue('Дивиденды и купоны до конца года');
	await expect(field).toBeFocused();
	await expect(page.getByRole('article')).toHaveCount(0);
	expect(errors).toEqual([]);
});
