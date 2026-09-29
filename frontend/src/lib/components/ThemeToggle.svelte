<script lang="ts">
	import Moon from '@lucide/svelte/icons/moon';
	import Sun from '@lucide/svelte/icons/sun';
	import { mode, toggleMode } from 'mode-watcher';
	import { Button } from '$lib/ui/button';

	const dark = $derived(mode.current === 'dark');
	const label = $derived(dark ? 'Светлая тема' : 'Тёмная тема');
</script>

<Button variant="ghost" size="icon-sm" aria-label={label} title={label} onclick={toggleMode}>
	{#if dark}
		<Sun />
	{:else}
		<Moon />
	{/if}
</Button>
