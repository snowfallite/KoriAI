import createClient from 'openapi-fetch';
import type { ApiError } from '$lib/types';
import type { paths } from './schema';

// The API shares the origin of the SPA (tech.md AD-01).
export const api = createClient<paths>({ credentials: 'same-origin' });

async function apiError(response: Response): Promise<ApiError> {
	// The API answers every error with ErrorOut (tech.md §6.1); a proxy may not.
	const body = await response.json().catch(() => undefined);
	if (typeof body?.code === 'string') return { ...body, status: response.status };
	return {
		code: 'internal',
		message: 'Сервер недоступен, попробуйте позже',
		details: null,
		request_id: response.headers.get('X-Request-Id') ?? '',
		status: response.status
	};
}

api.use({
	async onResponse({ response }) {
		if (response.ok) return;
		const error = await apiError(response);
		// A wrong password is a 401 too, but the login form shows it. A full load drops the
		// state of the lost session.
		if (error.code === 'unauthorized') location.assign('/login');
		throw error;
	}
});

/** The body of a call: the middleware above turns every error into a thrown ApiError. */
export async function ok<T>(call: Promise<{ data?: T }>): Promise<T> {
	return (await call).data as T;
}
