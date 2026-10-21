// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { BrokerAccountOut } from '$lib/types';
import AccountSelect from './AccountSelect.svelte';

function account(alias: string, name: string, is_hidden = false): BrokerAccountOut {
	return { alias, name, type: 'broker', status: 'open', opened_at: null, is_hidden };
}

const ACCOUNTS = [
	account('acc1', 'Брокерский счёт'),
	account('acc2', 'ИИС'),
	account('acc3', 'Закрытый', true)
];

const tabs = () => screen.getAllByRole('radio').map((tab) => tab.textContent?.trim());

describe('AccountSelect', () => {
	// tech.md §13.2 (v10): an account is signed with its name, the alias never shows.
	it('names the visible accounts and shows no alias', () => {
		const { container } = render(AccountSelect, {
			accounts: ACCOUNTS,
			value: null,
			onChange: vi.fn()
		});

		expect(tabs()).toEqual(['Все счета', 'Брокерский счёт', 'ИИС']);
		expect(container.textContent).not.toMatch(/acc\d/);
	});

	it('tells apart two accounts of one name', () => {
		render(AccountSelect, {
			accounts: [account('acc1', 'Брокерский счёт'), account('acc2', 'Брокерский счёт')],
			value: 'acc2',
			onChange: vi.fn()
		});

		expect(tabs()).toEqual(['Все счета', 'Брокерский счёт', 'Брокерский счёт (2)']);
	});

	it('hands back the alias of the chosen account', async () => {
		const onChange = vi.fn();
		render(AccountSelect, { accounts: ACCOUNTS, value: null, onChange });

		await fireEvent.click(screen.getByRole('radio', { name: 'ИИС' }));

		expect(onChange).toHaveBeenCalledWith('acc2');
	});
});
