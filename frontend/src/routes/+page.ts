import { redirect } from '@sveltejs/kit';

// The chat tab is the home of the app (tech.md §1).
export function load() {
	redirect(307, '/chat');
}
