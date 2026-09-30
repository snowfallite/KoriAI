import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';
import type { PageLoad } from './$types';

// Only a build with PUBLIC_KITCHEN_SINK=1 shows the page (tech.md §15.3).
export const load: PageLoad = () => {
	if (env.PUBLIC_KITCHEN_SINK !== '1') error(404, 'Not Found');
};
