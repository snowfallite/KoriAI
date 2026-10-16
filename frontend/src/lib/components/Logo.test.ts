// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Logo from './Logo.svelte';

const SIZES = ['sm', 'md', 'lg'] as const;

/** The seal 氷 of the logo (tech.md §13.2): decor, never read out. */
function sealOf(container: HTMLElement) {
	return container.querySelector('[data-slot="logo-seal"]');
}

describe('Logo', () => {
	it('sets the seal before the name in the compact form and reads only «Kōri»', () => {
		for (const size of SIZES) {
			const { container, unmount } = render(Logo, { size });
			const seal = sealOf(container);

			expect(seal?.getAttribute('aria-hidden')).toBe('true');
			expect(screen.getByText('Kōri')).toBeTruthy();
			unmount();
		}
	});

	it('gives the seal alone the name «Kōri»', () => {
		for (const size of SIZES) {
			const { container, unmount } = render(Logo, { variant: 'sign', size });

			expect(screen.getByRole('img', { name: 'Kōri' })).toBeTruthy();
			expect(sealOf(container)?.getAttribute('aria-hidden')).toBe('true');
			unmount();
		}
	});

	it('spaces K Ō R I with the kana between and reads it as one name', () => {
		const { container } = render(Logo, { variant: 'spaced' });
		const logo = screen.getByRole('img', { name: 'Kōri' });

		expect(logo.textContent).toContain('こ');
		for (const part of logo.querySelectorAll(':scope > *')) {
			expect(part.getAttribute('aria-hidden')).toBe('true');
		}
		expect(sealOf(container)).toBeNull();
	});
});
