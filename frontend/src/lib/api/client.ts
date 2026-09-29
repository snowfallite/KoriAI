import createClient from 'openapi-fetch';
import type { ApiError } from '$lib/types';
import type { paths } from './schema';

// The API shares the origin of the SPA (tech.md AD-01).
export const api = createClient<paths>({ credentials: 'same-origin' });

function internal(message: string, status: number, request_id = ''): ApiError {
	return { code: 'internal', message, details: null, request_id, status };
}

async function apiError(response: Response): Promise<ApiError> {
	// The API answers every error with ErrorOut (tech.md §6.1); a proxy may not.
	const body = await response.json().catch(() => undefined);
	if (typeof body?.code === 'string') return { ...body, status: response.status };
	const requestId = response.headers.get('X-Request-Id') ?? '';
	return internal('Сервер недоступен, попробуйте позже', response.status, requestId);
}

api.use({
	async onResponse({ response }) {
		if (response.ok) return;
		const error = await apiError(response);
		// A wrong password is a 401 too, but the login form shows it. A full load drops the
		// state of the lost session.
		if (error.code === 'unauthorized') location.assign('/login');
		throw error;
	},
	onError({ error }) {
		// fetch fails with a TypeError when the network is down; an abort stays an abort.
		if (error instanceof TypeError) throw internal('Нет связи с сервером', 0);
	}
});

/** The body of a call: the middleware above turns every error into a thrown ApiError. */
export async function ok<T>(call: Promise<{ data?: T }>): Promise<T> {
	return (await call).data as T;
}
