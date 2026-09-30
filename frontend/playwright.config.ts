import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: 'tests/e2e',
	use: {
		// The CI stack serves the built SPA and the API through Caddy (tech.md §14.3).
		baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
		trace: 'retain-on-failure'
	}
});
