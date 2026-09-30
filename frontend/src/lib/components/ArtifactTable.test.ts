// @vitest-environment jsdom
import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { TableSpec } from '$lib/types';
import ArtifactTable from './ArtifactTable.svelte';

const spec: TableSpec = {
	title: 'Позиции',
	columns: [
		{ key: 'ticker', label: 'Бумага', type: 'text', currency: null, digits: null },
		{ key: 'yield', label: 'Доходность', type: 'number', currency: null, digits: 0 }
	],
	rows: [
		{ ticker: 'SBER', yield: '3' },
		{ ticker: 'GAZP', yield: null },
		{ ticker: 'LKOH', yield: '10' }
	],
	total: null,
	note: null,
	instruments: {},
	source_ids: []
};

/** Tickers of the body rows, top to bottom. */
const tickers = (container: HTMLElement) =>
	[...container.querySelectorAll('tbody tr')].map((row) => row.querySelector('td')?.textContent);

describe('ArtifactTable', () => {
	it('sorts numbers by value and keeps an empty cell last in both directions', async () => {
		const { container, getByRole } = render(ArtifactTable, { spec });
		const header = getByRole('button', { name: 'Доходность' });

		await fireEvent.click(header);
		const first = tickers(container);
		await fireEvent.click(header);
		const second = tickers(container);

		expect([first, second]).toContainEqual(['SBER', 'LKOH', 'GAZP']);
		expect([first, second]).toContainEqual(['LKOH', 'SBER', 'GAZP']);
	});
});
