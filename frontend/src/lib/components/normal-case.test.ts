// @vitest-environment jsdom
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { Badge } from '$lib/ui/badge';
import * as Card from '$lib/ui/card';
import { Label } from '$lib/ui/label';
import { Toggle } from '$lib/ui/toggle';
import DataTable from './DataTable.svelte';
import Disclaimer from './Disclaimer.svelte';
import EmptyState from './EmptyState.svelte';
import PageHeader from './PageHeader.svelte';
import StatCard from './StatCard.svelte';
import UsageMeter from './UsageMeter.svelte';

// tech.md S1-15 AC 3: caps only in the column heads of tables and on the cover of the sign-in
// pages. The menu, buttons, field labels, meta lines, captions, the theme switch and the
// disclaimer speak in normal case.
const caps = (container: HTMLElement) =>
	[container, ...container.querySelectorAll('*')].filter((el) =>
		el.classList.contains('uppercase')
	);

describe('normal case', () => {
	it('keeps the composites out of caps', () => {
		const views = [
			render(PageHeader, { title: 'Портфель', description: 'Цены Т-Инвестиций на 10.10.2026' }),
			render(Disclaimer),
			render(StatCard, { label: 'Стоимость', value: '1 195 145 ₽', hint: 'все счета' }),
			render(UsageMeter, { label: 'Lite', used: 6_100_000, quota: 250_000_000, pace: 0.04 }),
			render(EmptyState, { title: 'Чата пока нет' })
		];
		for (const { container } of views) {
			expect(caps(container).map((el) => el.textContent)).toEqual([]);
		}
	});

	it('keeps the primitives out of caps', () => {
		const views = [
			render(Label, { for: 'email' }),
			render(Badge, { variant: 'link' }),
			render(Toggle, { 'aria-label': 'Жирный' }),
			render(Card.Title)
		];
		for (const { container } of views) {
			expect(caps(container)).toEqual([]);
		}
	});

	it('leaves the page header without decor', () => {
		const { container } = render(PageHeader, { title: 'Чат' });

		expect(container.querySelector('[lang="ja"]')).toBeNull();
		expect(container.querySelector('h1')?.textContent).toBe('Чат');
	});

	it('sets the column heads in caps', () => {
		const { container } = render(DataTable<{ ticker: string }>, {
			columns: [{ accessorKey: 'ticker', header: 'Тикер' }],
			rows: [{ ticker: 'SBER' }]
		});

		expect(container.querySelector('th')?.className).toContain('uppercase');
	});
});
