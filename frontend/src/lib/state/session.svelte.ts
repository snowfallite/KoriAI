import { toast } from 'svelte-sonner';
import { api, ok } from '$lib/api/client';
import type { ApiError } from '$lib/types';

/** Ends the session. A full load of /login drops its state, as client.ts does on a 401. */
export async function signOut(): Promise<void> {
	try {
		await ok(api.POST('/api/auth/logout'));
		location.assign('/login');
	} catch (error) {
		toast.error((error as ApiError).message);
	}
}
