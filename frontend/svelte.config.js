import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Runes everywhere except dependencies (tech.md §16.2). Can go away in Svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// SPA behind Caddy: every route falls back to one HTML shell (tech.md AD-01).
		adapter: adapter({ fallback: '200.html' }),
		// The shell carries the policy as a meta tag with the hash of its boot script; Caddy
		// adds frame-ancestors, which a meta tag cannot set (tech.md §3.5).
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				'img-src': ['self', 'data:'],
				'style-src': ['self', 'unsafe-inline'],
				'connect-src': ['self']
			}
		}
	}
};

export default config;
