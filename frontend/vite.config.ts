import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	// svelteTesting: browser Svelte and DOM cleanup for component tests (jsdom per file).
	plugins: [tailwindcss(), sveltekit(), svelteTesting()],
	// The dev API from docker-compose.dev.yml (tech.md §15.1).
	server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
	test: {
		include: ['src/**/*.test.ts'],
		passWithNoTests: true,
		expect: { requireAssertions: true }
	}
});
