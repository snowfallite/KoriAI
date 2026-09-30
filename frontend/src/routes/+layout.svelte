<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import favicon from '$lib/assets/favicon.svg';
	import { Toaster } from '$lib/ui/sonner';

	let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<!-- The SPA sets the theme class from JS; a head script would add nothing but a CSP hash. -->
<ModeWatcher disableHeadScriptInjection />
<Toaster />
{@render children()}
