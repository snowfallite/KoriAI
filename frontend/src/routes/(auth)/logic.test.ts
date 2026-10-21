import { describe, expect, it } from 'vitest';
import type { ApiError } from '$lib/types';
import { CANDLES, candleShapes, fieldError } from './logic';

function apiError(code: ApiError['code'], message: string, details: ApiError['details'] = null) {
	return { code, message, details, request_id: 'r1', status: 400 } as ApiError;
}

// S1-14 AC 4: an error the API ties to a field shows at that field (docs/ui-references/kori-v3).
describe('fieldError', () => {
	it('puts a wrong password, a taken email and a bad invite at their fields', () => {
		expect(fieldError(apiError('invalid_credentials', 'Неверный email или пароль'))).toEqual({
			field: 'password',
			message: 'Неверный email или пароль'
		});
		expect(fieldError(apiError('email_taken', 'Этот email уже зарегистрирован'))).toEqual({
			field: 'email',
			message: 'Этот email уже зарегистрирован'
		});
		for (const code of ['invite_required', 'invite_invalid'] as const) {
			expect(fieldError(apiError(code, 'Нужен код приглашения'))?.field).toBe('invite');
		}
	});

	it('finds the field of a validation error by its location', () => {
		const short = apiError('validation_error', 'Проверьте введённые данные', {
			errors: [{ loc: ['body', 'password'], msg: 'too short', type: 'string_too_short' }]
		});
		expect(fieldError(short)).toEqual({ field: 'password', message: 'Не короче 10 символов' });
	});

	it('leaves an error without a field to the form', () => {
		for (const error of [
			apiError('rate_limited', 'Слишком много попыток'),
			apiError('registration_closed', 'Регистрация закрыта'),
			apiError('validation_error', 'Проверьте введённые данные', { errors: [{ loc: ['body'] }] }),
			apiError('validation_error', 'Проверьте введённые данные', { errors: 'bad' }),
			apiError('internal', 'Нет связи с сервером')
		]) {
			expect(fieldError(error)).toBeNull();
		}
	});
});

// The scene «свет над графиком» (tech.md S1-15 AC 5, docs/ui-references/kori-v4/README.md):
// 30 columns 48 px apart, bodies 34 px wide and a whole number of 28 px high, a path from y 616
// to y 168 in the 1440 × 900 box of html/login.html; y grows downwards.
describe('CANDLES', () => {
	it('stands 30 candles in columns 48 px apart', () => {
		expect(CANDLES).toHaveLength(30);
		CANDLES.forEach((candle, i) => expect(candle.x).toBe(7 + 48 * i));
	});

	it('walks from y 616 to y 168, each candle opening at the close of the one before', () => {
		expect(CANDLES[0]?.open).toBe(616);
		expect(CANDLES.at(-1)?.close).toBe(168);
		CANDLES.slice(1).forEach((candle, i) => expect(candle.open).toBe(CANDLES[i]?.close));
	});

	it('gives every body a whole number of 28 px and keeps the wicks outside it', () => {
		for (const { open, close, high, low } of CANDLES) {
			expect(Math.abs(open - close) % 28).toBe(0);
			expect(open).not.toBe(close);
			expect(high).toBeLessThanOrEqual(Math.min(open, close));
			expect(low).toBeGreaterThanOrEqual(Math.max(open, close));
		}
	});

	it('rises 18 times and falls 12 times', () => {
		expect(CANDLES.filter((candle) => candle.close < candle.open)).toHaveLength(18);
	});
});

describe('candleShapes', () => {
	// The first and the third candle of html/login.html, coordinates as the mockup draws them.
	it('draws a rise as a hollow body and a fall as a filled one, with their wicks', () => {
		const [rise, , fall] = CANDLES;

		expect(rise && candleShapes(rise)).toEqual({
			rise: true,
			body: { x: 7.5, y: 532.5, width: 33, height: 83 },
			wicks: [{ x: 24.5, y1: 518, y2: 533 }]
		});
		expect(fall && candleShapes(fall)).toEqual({
			rise: false,
			body: { x: 103, y: 448, width: 34, height: 56 },
			wicks: [
				{ x: 120.5, y1: 420, y2: 448 },
				{ x: 120.5, y1: 504, y2: 518 }
			]
		});
	});
});
