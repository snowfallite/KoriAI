<script lang="ts">
	import '../app.css';
	import { ModeWatcher, setMode, userPrefersMode } from 'mode-watcher';
	import { onMount } from 'svelte';
	import favicon from '$lib/assets/favicon.svg';
	import { Toaster } from '$lib/ui/sonner';

	let { children } = $props();

	// Night is the Kïoku default. mode-watcher stores 'system' before it reads defaultMode, and
	// ThemeToggle only ever stores light or dark, so 'system' means the reader never chose.
	onMount(() => {
		if (userPrefersMode.current === 'system') setMode('dark');
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<!-- app.html starts dark, so the SPA needs no head script (and no CSP hash for it). -->
<ModeWatcher disableHeadScriptInjection />
<Toaster />
{@render children()}
