// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { SourceRef } from '$lib/types';
import SourceList from './SourceList.svelte';

function source(fields: Partial<SourceRef> & Pick<SourceRef, 'local_id' | 'kind'>): SourceRef {
	return {
		title: 'портфель',
		url: null,
		publisher: null,
		published_at: null,
		document_id: null,
		page: null,
		snippet: null,
		...fields
	};
}

describe('SourceList', () => {
	// tech.md §13.2 (v10): the number and «publisher, title, date, page» with commas, no arrow.
	it('lists each source as a number and a line with commas', () => {
		render(SourceList, {
			sources: [
				source({
					local_id: 's1',
					kind: 'tinvest',
					publisher: 'Т-Инвестиции',
					published_at: '2026-10-10',
					url: 'https://www.tbank.ru/invest/'
				}),
				source({ local_id: 's2', kind: 'document', title: 'МСФО за 2025 год', page: 12 })
			]
		});
		const items = screen.getAllByRole('listitem');

		expect(items.map((item) => item.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'1 Т-Инвестиции, портфель, 10.10.2026',
			'2 документ, МСФО за 2025 год, стр. 12'
		]);
		for (const item of items) expect(item.textContent).not.toMatch(/[→·]/);
		expect(screen.getByRole('link').getAttribute('href')).toBe('https://www.tbank.ru/invest/');
	});
});
