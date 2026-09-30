// @vitest-environment jsdom
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import MoneyText from './MoneyText.svelte';

const NBSP = '\u00a0';

function text(
	amount: string,
	props: { signed?: boolean; compact?: boolean; colorize?: boolean } = {}
) {
	return render(MoneyText, { money: { amount, currency: 'RUB' }, ...props }).container
		.firstElementChild as HTMLElement;
}

describe('MoneyText', () => {
	it('prints the amount in its currency', () => {
		expect(text('1250000').textContent).toBe(`1${NBSP}250${NBSP}000,00${NBSP}₽`);
	});

	it('adds a plus to a signed gain and a minus sign to a loss', () => {
		expect(text('1250.5', { signed: true }).textContent).toBe(`+1${NBSP}250,50${NBSP}₽`);
		expect(text('-1250.5').textContent).toBe(`\u22121${NBSP}250,50${NBSP}₽`);
	});

	it('compacts big amounts', () => {
		expect(text('1250000', { compact: true }).textContent).toBe(`1,25${NBSP}млн${NBSP}₽`);
	});

	it('colors gains and losses only when asked', () => {
		expect(text('10', { colorize: true }).className).toContain('text-positive');
		expect(text('-10', { colorize: true }).className).toContain('text-negative');
		expect(text('0', { colorize: true }).className).not.toMatch(/text-(positive|negative)/);
		expect(text('-10').className).not.toContain('text-negative');
	});
});
