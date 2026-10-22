import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { ApiError } from '$lib/types';
import { accountNote, checkedAt, connectedNote, TOKEN_HELP, tokenError } from './logic';

function apiError(code: ApiError['code'], message: string): ApiError {
	return { code, message, details: null, request_id: 'r1', status: 422 };
}

// kori-v4, Уведомления: «Т-Инвестиции подключены, найдено 2 счёта».
describe('connectedNote', () => {
	it('agrees the count with its noun', () => {
		const note = (count: number) => connectedNote(count).replace('Т-Инвестиции подключены, ', '');
		expect(note(1)).toBe('найден 1 счёт');
		expect(note(2)).toBe('найдено 2 счёта');
		expect(note(4)).toBe('найдено 4 счёта');
		expect(note(5)).toBe('найдено 5 счетов');
		expect(note(11)).toBe('найдено 11 счетов');
		expect(note(21)).toBe('найден 21 счёт');
		expect(note(22)).toBe('найдено 22 счёта');
		expect(note(112)).toBe('найдено 112 счетов');
	});

	it('names the count of any connection', () => {
		fc.assert(
			fc.property(fc.integer({ min: 0, max: 100_000 }), (count) => {
				const note = connectedNote(count);
				expect(note.startsWith('Т-Инвестиции подключены, найден')).toBe(true);
				// format.ts groups thousands with a no-break space.
				expect(note.replace(/(\d)\s(?=\d)/gu, '$1')).toContain(` ${count} сч`);
			})
		);
	});
});

// tech.md §6.3: PUT /api/broker/connection refuses a token with 422, T-Invest fails with 503.
describe('tokenError', () => {
	it('puts what is wrong with the token at its field', () => {
		for (const code of ['token_invalid', 'token_not_read_only', 'validation_error'] as const) {
			expect(tokenError(apiError(code, 'Причина'))).toBe('Причина');
		}
	});

	it('leaves a failure of T-Invest or the server to the form', () => {
		for (const code of ['tinvest_unavailable', 'tinvest_rate_limited', 'internal'] as const) {
			expect(tokenError(apiError(code, 'Т-Инвестиции не отвечают'))).toBeNull();
		}
	});
});

describe('checkedAt', () => {
	it('shows the last check in Moscow time', () => {
		expect(checkedAt('2026-10-22T16:00:00Z')).toBe('22.10.2026, 19:00 МСК');
	});

	it('shows a dash for a connection nobody checked yet', () => {
		expect(checkedAt(null)).toBe('—');
	});
});

describe('accountNote', () => {
	it('notes an account that is not open', () => {
		expect(accountNote('open')).toBeNull();
		expect(accountNote('closed')).toBe('закрыт');
		expect(accountNote('new')).toBe('открывается');
		expect(accountNote('other')).toBe('статус неизвестен');
	});
});

it('leads to the token page of T-Invest', () => {
	expect(TOKEN_HELP).toBe('https://developer.tbank.ru/invest/intro/intro/token');
});
