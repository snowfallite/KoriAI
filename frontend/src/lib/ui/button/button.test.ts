// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import GlyphButton from './glyph-button.test.svelte';
import type { ButtonVariant } from './index';

const VARIANTS = ['default', 'destructive', 'secondary', 'outline', 'ghost', 'link', 'ai'] as const;
const CELL = '[&>[data-slot=button-glyph]]:';
// A solid red field: the brand red, red-deep or the red of errors (tech.md §13.1, S1-14 AC 1).
const RED = /^(bg-(primary|primary-deep|destructive|negative)|ki-(ignite|ember|hero|tile))$/;

/** The classes the button wears at rest, and those it gives its glyph cell. */
function classesOf(button: HTMLElement) {
	const tokens = button.className.split(/\s+/).filter(Boolean);
	return {
		own: tokens.filter((t) => !t.includes(':')),
		cell: tokens.filter((t) => t.startsWith(CELL)).map((t) => t.slice(CELL.length))
	};
}

function renderButton(variant: ButtonVariant) {
	render(GlyphButton, { variant });
	return screen.getByRole('button', { name: 'Войти' });
}

describe('Button', () => {
	it('puts the glyph in a cell first and keeps it out of the name', () => {
		const button = renderButton('default');
		const cell = button.firstElementChild;

		expect(cell?.getAttribute('data-slot')).toBe('button-glyph');
		expect(cell?.getAttribute('aria-hidden')).toBe('true');
		expect(button.textContent).toBe('→Войти');
	});

	it('gives the main action a red cell and a label in the ink color', () => {
		const { own, cell } = classesOf(renderButton('default'));

		expect(cell).toContain('bg-primary');
		expect(own).toContain('bg-foreground');
		expect(own).toContain('text-background');
	});

	// The variants merge with a config that knows the type scale (lib/utils/cn.ts).
	it('keeps the 13 px label next to its ink color', () => {
		const { own } = classesOf(renderButton('default'));

		expect(own).toContain('text-ui');
		expect(own).toContain('text-background');
	});

	it('gives the destructive action the red-deep cell and the same ink label', () => {
		const { own, cell } = classesOf(renderButton('destructive'));

		expect(cell).toContain('bg-primary-deep');
		expect(own).toContain('bg-foreground');
	});

	// tech.md S1-15 AC 2: a glyph stands only where it means something, so the cell comes only
	// from a button-glyph child; Отмена and secondary actions show their label alone.
	it('draws a cell only from a button-glyph child', () => {
		for (const variant of VARIANTS) {
			const { unmount } = render(GlyphButton, { variant, glyph: null, label: 'Отмена' });
			const button = screen.getByRole('button', { name: 'Отмена' });

			expect(button.querySelector('[data-slot="button-glyph"]'), variant).toBeNull();
			expect(button.textContent, variant).toBe('Отмена');
			// No glyph sneaks in through generated content either.
			expect(button.className, variant).not.toMatch(/(^|\s)(\S+:)?(before|after):content-/);
			unmount();
		}
	});

	// S1-15 AC 3: caps stay in the column heads and on the cover; buttons speak in normal case.
	it('sets no variant in caps', () => {
		for (const variant of VARIANTS) {
			const { unmount } = render(GlyphButton, { variant, glyph: null, label: 'Повторить' });
			const { own } = classesOf(screen.getByRole('button', { name: 'Повторить' }));

			expect(own, variant).not.toContain('uppercase');
			unmount();
		}
	});

	it('rests on no solid red field in any variant', () => {
		for (const variant of VARIANTS) {
			const { unmount } = render(GlyphButton, { variant });
			const { own } = classesOf(screen.getByRole('button', { name: 'Войти' }));
			expect(
				own.filter((token) => RED.test(token)),
				variant
			).toEqual([]);
			unmount();
		}
	});
});
