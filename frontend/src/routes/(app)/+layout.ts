import { redirect } from '@sveltejs/kit';
import { api, ok } from '$lib/api/client';
import type { ApiError } from '$lib/types';
import type { LayoutLoad } from './$types';

// Every tab works for the signed-in user only (tech.md §6.1).
export const load: LayoutLoad = async ({ depends }) => {
	depends('app:me');
	try {
		return { me: await ok(api.GET('/api/auth/me')) };
	} catch (error) {
		// client.ts has started a full load of /login; the redirect skips the error page meanwhile.
		if ((error as ApiError).code === 'unauthorized') redirect(307, '/login');
		throw error;
	}
};
