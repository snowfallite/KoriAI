// @vitest-environment jsdom
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { SourceRef } from '$lib/types';
import Markdown from './Markdown.svelte';

function source(local_id: string, url: string | null): SourceRef {
	return {
		local_id,
		kind: 'web',
		title: `Источник ${local_id}`,
		url,
		publisher: null,
		published_at: null,
		document_id: null,
		page: null,
		snippet: null
	};
}

function view(text: string, sources: SourceRef[] = []): HTMLElement {
	return render(Markdown, { source: text, sources }).container;
}

describe('Markdown', () => {
	it('prints raw HTML as text and runs no script', () => {
		const el = view(
			'<script>window.hacked = true</script>\n\nтекст <b>жирный</b> <svg onload="x()">'
		);

		expect(el.querySelector('script, b, svg')).toBeNull();
		expect(el.textContent).toContain('<script>window.hacked = true</script>');
		expect(el.textContent).toContain('<b>жирный</b>');
		expect((window as { hacked?: boolean }).hacked).toBeUndefined();
	});

	it('hides images of the text, markdown and HTML alike', () => {
		const el = view(
			'![лого](https://example.com/a.png)\n\n<img src="x" onerror="window.hacked = true">'
		);

		expect(el.querySelector('img')).toBeNull();
	});

	it('keeps only http(s) links and opens them in a new tab without referrer', () => {
		const el = view(
			'[сайт](https://example.com) [скрипт](javascript:alert(1)) [данные](data:text/html,x) ' +
				'[почта](mailto:a@b.c) <a href="https://example.com/raw">сырой</a> https://example.org'
		);
		const links = [...el.querySelectorAll('a')];

		expect(links.map((a) => a.getAttribute('href'))).toEqual([
			'https://example.com',
			'https://example.org'
		]);
		for (const a of links) {
			expect(a.getAttribute('target')).toBe('_blank');
			expect(a.getAttribute('rel')).toBe('noopener noreferrer nofollow');
		}
		expect(el.textContent).toContain('скрипт');
	});

	it('turns known citations into footnotes and hides unknown ones', () => {
		const el = view('Выручка выросла [s1], маржа [s2], прибыль [s9]. Код `[s1]`.', [
			source('s1', 'https://example.com/news'),
			source('s2', null)
		]);
		const notes = [...el.querySelectorAll('sup')];

		expect(notes.map((n) => n.textContent)).toEqual(['1', '2']);
		expect(notes[0]?.querySelector('a')?.getAttribute('href')).toBe('https://example.com/news');
		expect(notes[1]?.querySelector('a')).toBeNull();
		expect(el.textContent).not.toContain('[s9]');
		expect(el.querySelector('code')?.textContent).toBe('[s1]');
	});

	// docs/ui-references/kori-v4: the answer is grey prose, its numbers in the ink color, losses red.
	it('sets numbers in the ink color and losses in red', () => {
		const el = view(
			'Портфель стоит 1 195 145 ₽, Газпром дал −23 800 ₽ и -14,7 %, доля 11,6 %. ' +
				'На 10.10.2026 в 19:00.'
		);
		const numbers = [...el.querySelectorAll('[data-number]')];

		expect(numbers.map((n) => [n.textContent, n.getAttribute('data-number')])).toEqual([
			['1 195 145 ₽', 'value'],
			['−23 800 ₽', 'loss'],
			['-14,7 %', 'loss'],
			['11,6 %', 'value'],
			['10.10.2026', 'value'],
			['19:00', 'value']
		]);
		expect(el.textContent).toContain('Портфель стоит 1 195 145 ₽, Газпром дал −23 800 ₽');
	});

	it('leaves digits inside words, names and ranges as text', () => {
		const el = view('GigaChat-2-Pro, счёт acc1, годы 2020-2025, код `42`, ссылка [s1].', [
			source('s1', 'https://example.com')
		]);

		expect([...el.querySelectorAll('[data-number]')].map((n) => n.textContent)).toEqual(['2020']);
	});

	// tech.md S1-15 AC 4: the prose is Noto Serif, its numbers JetBrains Mono, lists plain.
	it('sets the prose in serif and every number in a mono span', () => {
		const el = view('Газпром дал −23 800 ₽ при доле 11,6 %.');
		const prose = el.firstElementChild as HTMLElement;
		const numbers = [...el.querySelectorAll('[data-number]')];

		expect(prose.className).toContain('font-serif');
		expect(numbers.map((n) => n.textContent)).toEqual(['−23 800 ₽', '11,6 %']);
		for (const number of numbers) {
			expect(number.className).toContain('font-mono');
		}
	});

	it('keeps the ordinary markers of lists', () => {
		const el = view('- выручка\n- прибыль\n\n1. первый\n2. второй');
		const prose = el.firstElementChild as HTMLElement;

		expect(el.querySelectorAll('ul > li')).toHaveLength(2);
		expect(el.querySelectorAll('ol > li')).toHaveLength(2);
		expect(prose.className).toContain('[&_ul]:list-disc');
		expect(prose.className).toContain('[&_ol]:list-decimal');
		expect(prose.className).not.toMatch(/list-\['/);
	});

	it('sets block headings in bold mono', () => {
		const el = view('### Что тянет вверх и вниз\n\nТекст.');
		const prose = el.firstElementChild as HTMLElement;

		expect(el.querySelector('h3')?.textContent).toBe('Что тянет вверх и вниз');
		expect(prose.className).toContain('[&_h3]:font-mono');
		expect(prose.className).toContain('[&_h3]:font-bold');
	});

	it('marks a key phrase between double equals signs', () => {
		const el = view('Итог: ==прибыль +42 090 ₽== за год.');
		const mark = el.querySelector('mark');

		expect(mark?.textContent).toBe('прибыль +42 090 ₽');
		expect(mark?.querySelector('[data-number]')?.textContent).toBe('+42 090 ₽');
		expect(el.textContent).not.toContain('==');
	});

	it('renders a code block with a copy button', () => {
		const el = view('```ts\nconst a = 1\n```');

		expect(el.querySelector('pre code')?.textContent).toContain('const a = 1');
		expect(el.querySelector('button[aria-label="Копировать"]')).not.toBeNull();
	});
});
