import { redirect } from '@sveltejs/kit';

// The chat tab is the home of the app (tech.md §1); until F-03 builds it, the portfolio is the
// first screen that answers anything (tech.md S1-15).
export function load() {
	redirect(307, '/portfolio');
}
