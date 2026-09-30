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

	it('renders a code block with a copy button', () => {
		const el = view('```ts\nconst a = 1\n```');

		expect(el.querySelector('pre code')?.textContent).toContain('const a = 1');
		expect(el.querySelector('button[aria-label="Копировать"]')).not.toBeNull();
	});
});
