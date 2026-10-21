import { error, redirect } from '@sveltejs/kit';
import { api, ok } from '$lib/api/client';
import type { ApiError } from '$lib/types';
import type { LayoutLoad } from './$types';

// Every tab works for the signed-in user only (tech.md §6.1).
export const load: LayoutLoad = async ({ depends }) => {
	depends('app:me');
	try {
		return { me: await ok(api.GET('/api/auth/me')) };
	} catch (failure) {
		const reason = failure as ApiError;
		// client.ts has started a full load of /login; the redirect skips the error page meanwhile.
		if (reason.code === 'unauthorized') redirect(307, '/login');
		if (typeof reason.code !== 'string') throw failure;
		// The error page says what failed and gives the request code (tech.md S1-15 AC 8); a lost
		// network has no status of its own.
		error(reason.status >= 400 && reason.status <= 599 ? reason.status : 503, {
			message: reason.message,
			request_id: reason.request_id || undefined
		});
	}
};
