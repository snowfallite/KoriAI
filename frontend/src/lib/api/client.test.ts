import { beforeEach, describe, expect, expectTypeOf, it, vi } from 'vitest';
import { api, ok } from './client';
import type { components } from './schema';

const BASE = 'http://kori.test';

function answer(status: number, body: unknown, headers: Record<string, string> = {}) {
	const text = typeof body === 'string' ? body : JSON.stringify(body);
	const init = { status, headers: { 'X-Request-Id': 'req-1', ...headers } };
	return vi.fn<(request: Request) => Promise<Response>>(async () => new Response(text, init));
}

function errorOut(code: string, message: string) {
	return { code, message, details: null, request_id: 'req-1' };
}

const assign = vi.fn();

beforeEach(() => {
	assign.mockClear();
	vi.stubGlobal('location', { assign });
});

describe('api client', () => {
	it('returns the body of a 2xx answer and sends same-origin credentials', async () => {
		const fetch = answer(200, { status: 'ok' });

		const health = await ok(api.GET('/api/health', { baseUrl: BASE, fetch }));

		expectTypeOf(health).toEqualTypeOf<components['schemas']['HealthOut']>();
		expect(health).toEqual({ status: 'ok' });
		expect(fetch.mock.calls[0]?.[0].credentials).toBe('same-origin');
	});

	it('leads to /login on 401 unauthorized and throws ApiError', async () => {
		const fetch = answer(401, errorOut('unauthorized', 'Войдите снова'));

		await expect(api.GET('/api/health', { baseUrl: BASE, fetch })).rejects.toEqual({
			...errorOut('unauthorized', 'Войдите снова'),
			status: 401
		});
		expect(assign).toHaveBeenCalledWith('/login');
	});

	it('stays on the page on 401 invalid_credentials', async () => {
		const fetch = answer(401, errorOut('invalid_credentials', 'Неверный email или пароль'));

		await expect(api.GET('/api/health', { baseUrl: BASE, fetch })).rejects.toMatchObject({
			code: 'invalid_credentials',
			status: 401
		});
		expect(assign).not.toHaveBeenCalled();
	});

	it('throws the ErrorOut of any other error with its status', async () => {
		const fetch = answer(503, errorOut('tinvest_unavailable', 'Т-Инвестиции недоступны'));

		await expect(api.GET('/api/health', { baseUrl: BASE, fetch })).rejects.toEqual({
			...errorOut('tinvest_unavailable', 'Т-Инвестиции недоступны'),
			status: 503
		});
	});

	it('turns an answer without ErrorOut into an internal ApiError', async () => {
		const fetch = answer(502, '<html>Bad Gateway</html>', { 'Content-Type': 'text/html' });

		await expect(api.GET('/api/health', { baseUrl: BASE, fetch })).rejects.toMatchObject({
			code: 'internal',
			request_id: 'req-1',
			status: 502
		});
	});
});
