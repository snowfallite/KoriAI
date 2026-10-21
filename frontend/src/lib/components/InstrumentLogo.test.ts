// @vitest-environment jsdom
import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import InstrumentLogo from './InstrumentLogo.svelte';

/** jsdom loads no images: this stand-in answers the avatar's probe the way a browser would. */
function stubImages(loads: boolean) {
	vi.stubGlobal(
		'Image',
		class {
			onload: (() => void) | null = null;
			onerror: (() => void) | null = null;
			set src(_: string) {
				setTimeout(() => (loads ? this.onload?.() : this.onerror?.()));
			}
		}
	);
}

function fallbackOf(container: HTMLElement): HTMLElement | null {
	return container.querySelector('[data-slot="avatar-fallback"]');
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('InstrumentLogo', () => {
	// tech.md §13.2: initials on the neutral grey-900 tile; the brand color paints nothing.
	it('shows initials in white on the neutral tile, whatever the brand color', () => {
		const { container } = render(InstrumentLogo, {
			src: null,
			name: 'Газпром нефть',
			color: '#1a9f29'
		});
		const fallback = fallbackOf(container);
		const classes = fallback?.className.split(/\s+/) ?? [];

		expect(fallback?.textContent?.trim()).toBe('ГН');
		expect(classes).toContain('bg-grey-900');
		expect(classes).toContain('text-white');
		expect(fallback?.style.backgroundColor).toBe('');
		expect(container.querySelector('img')).toBeNull();
	});

	it('takes two letters of a one-word name', () => {
		const { container } = render(InstrumentLogo, { src: null, name: 'сбербанк' });

		expect(fallbackOf(container)?.textContent?.trim()).toBe('СБ');
	});

	// tech.md S1-15 AC 6: an OFZ tile reads «ОФЗ», a currency tile its code.
	it('names the tile of an OFZ and of a currency', () => {
		const tiles: [string, string][] = [
			['ОФЗ 26240', 'ОФЗ'],
			['ОФЗ 29024', 'ОФЗ'],
			['Доллар США', 'USD'],
			['Евро', 'EUR'],
			['Китайский юань', 'CNY'],
			['Российский рубль', 'RUB']
		];
		for (const [name, tile] of tiles) {
			const { container, unmount } = render(InstrumentLogo, { src: null, name });

			expect(fallbackOf(container)?.textContent?.trim(), name).toBe(tile);
			unmount();
		}
	});

	// docs/ui-references/kori-v4 (Портфель): Т-Технологии stand as «Т», not «Т-».
	it('stops a one-word name at its hyphen', () => {
		const { container } = render(InstrumentLogo, { src: null, name: 'Т-Технологии' });

		expect(fallbackOf(container)?.textContent?.trim()).toBe('Т');
	});

	it('falls back to initials when the logo fails to load', async () => {
		stubImages(false);
		const { container } = render(InstrumentLogo, { src: '/api/media/logos/x', name: 'Сбербанк' });

		await vi.waitFor(() => expect(container.querySelector('[data-status="error"]')).not.toBeNull());
		expect(fallbackOf(container)?.style.display).not.toBe('none');
		expect(fallbackOf(container)?.textContent?.trim()).toBe('СБ');
	});

	it('shows the logo once it loads', async () => {
		stubImages(true);
		const { container } = render(InstrumentLogo, { src: '/api/media/logos/x', name: 'Сбербанк' });

		await vi.waitFor(() => expect(container.querySelector('img')?.style.display).toBe('block'));
		expect(container.querySelector('img')?.getAttribute('alt')).toBe('Сбербанк');
		expect(fallbackOf(container)?.style.display).toBe('none');
	});
});
