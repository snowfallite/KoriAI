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
	it('shows initials on the brand color without a logo', () => {
		const { container } = render(InstrumentLogo, {
			src: null,
			name: 'Газпром нефть',
			color: '#1a9f29'
		});
		const fallback = fallbackOf(container);

		expect(fallback?.textContent?.trim()).toBe('ГН');
		expect(fallback?.style.backgroundColor).toBe('rgb(26, 159, 41)');
		expect(container.querySelector('img')).toBeNull();
	});

	it('takes two letters of a one-word name', () => {
		const { container } = render(InstrumentLogo, { src: null, name: 'сбербанк' });

		expect(fallbackOf(container)?.textContent?.trim()).toBe('СБ');
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
