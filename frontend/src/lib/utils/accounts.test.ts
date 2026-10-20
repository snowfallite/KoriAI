import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { accountNames } from './accounts';

const account = (alias: string, name: string) => ({ alias, name });

// tech.md §13.3: an account is called by its name; the alias acc1 never shows (S1-15 AC 6).
describe('accountNames', () => {
	it('names each account by its name', () => {
		const names = accountNames([account('acc1', 'Брокерский счёт'), account('acc2', 'ИИС')]);

		expect([...names]).toEqual([
			['acc1', 'Брокерский счёт'],
			['acc2', 'ИИС']
		]);
	});

	it('numbers a repeated name in the order of the accounts', () => {
		const names = accountNames([
			account('acc1', 'Брокерский счёт'),
			account('acc2', 'Брокерский счёт'),
			account('acc3', 'ИИС'),
			account('acc4', 'Брокерский счёт')
		]);

		expect([...names.values()]).toEqual([
			'Брокерский счёт',
			'Брокерский счёт (2)',
			'ИИС',
			'Брокерский счёт (3)'
		]);
	});

	it('gives every account its own label, whatever the names', () => {
		const name = fc.constantFrom('ИИС', 'ИИС (2)', 'Брокерский счёт', 'Брокерский счёт (3)', '');
		fc.assert(
			fc.property(fc.array(name, { maxLength: 8 }), (list) => {
				const names = accountNames(list.map((n, i) => account(`acc${i + 1}`, n)));
				const labels = [...names.values()];

				expect(names.size).toBe(list.length);
				expect(new Set(labels).size).toBe(labels.length);
				for (const label of labels) expect(label).not.toMatch(/acc\d/);
			})
		);
	});
});
