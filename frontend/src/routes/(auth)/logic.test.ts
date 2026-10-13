import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { ApiError } from '$lib/types';
import { fieldError, lengthHint } from './logic';

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

describe('lengthHint', () => {
	it('declines the count of characters', () => {
		expect(lengthHint(0)).toBe('0 символов · минимум 10');
		expect(lengthHint(1)).toBe('1 символ · минимум 10');
		expect(lengthHint(3)).toBe('3 символа · минимум 10');
		expect(lengthHint(12)).toBe('12 символов · минимум 10');
		expect(lengthHint(22)).toBe('22 символа · минимум 10');
	});

	it('names the count it gets for any length', () => {
		fc.assert(
			fc.property(fc.nat({ max: 1000 }), (n) => {
				expect(lengthHint(n)).toMatch(new RegExp(`^${n} символ(|а|ов) · минимум 10$`));
			})
		);
	});
});
