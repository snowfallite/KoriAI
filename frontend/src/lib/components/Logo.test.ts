// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Logo from './Logo.svelte';

const SIZES = ['sm', 'md', 'lg'] as const;
const VARIANTS = ['compact', 'spaced', 'sign'] as const;

describe('Logo', () => {
	// tech.md S1-15 AC 1: the product is named «Kōri», the seal 氷 is gone.
	it('draws no seal 氷 in any form or size', () => {
		for (const variant of VARIANTS) {
			for (const size of SIZES) {
				const { container, unmount } = render(Logo, { variant, size });

				expect(container.textContent, `${variant} ${size}`).not.toContain('氷');
				expect(container.querySelector('[data-slot="logo-seal"], path')).toBeNull();
				unmount();
			}
		}
	});

	it('writes the compact name as the text «Kōri»', () => {
		for (const size of SIZES) {
			const { unmount } = render(Logo, { size });

			expect(screen.getByText('Kōri')).toBeTruthy();
			unmount();
		}
	});

	// S1-15 AC 9: the spaced name and the sign read as «Kōri», their parts stay silent.
	it('spaces K Ō R I with the kana between and hides every part from the reader', () => {
		render(Logo, { variant: 'spaced' });
		const logo = screen.getByRole('img', { name: 'Kōri' });
		const kana = [...logo.querySelectorAll('[lang="ja"]')];

		expect(kana.map((k) => k.textContent)).toEqual(['こ', 'お', 'り']);
		expect(logo.textContent?.replace(/\s/g, '')).toBe('KŌRIこおり');
		for (const part of logo.querySelectorAll(':scope > *')) {
			expect(part.getAttribute('aria-hidden')).toBe('true');
		}
	});

	it('signs as «Kō» on the red-deep square', () => {
		for (const size of SIZES) {
			const { unmount } = render(Logo, { variant: 'sign', size });
			const sign = screen.getByRole('img', { name: 'Kōri' });

			expect(sign.textContent?.trim()).toBe('Kō');
			expect(sign.className).toContain('bg-primary-deep');
			unmount();
		}
	});
});
