import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Runes everywhere except dependencies (tech.md §16.2). Can go away in Svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// SPA behind Caddy: every route falls back to one HTML shell (tech.md AD-01).
		adapter: adapter({ fallback: '200.html' })
	}
};

export default config;
