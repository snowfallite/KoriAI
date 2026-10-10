<script lang="ts">
	import { mode } from 'mode-watcher';
	import { Toaster as Sonner, type ToasterProps as SonnerProps } from 'svelte-sonner';
	import Loader2Icon from '@lucide/svelte/icons/loader-2';

	let { ...restProps }: SonnerProps = $props();
</script>

<!-- Toasts speak like the notifications of v3: a row on the accent with a glyph cell. -->
<Sonner
	theme={mode.current}
	class="toaster group"
	style="--normal-bg: var(--color-accent); --normal-text: var(--color-foreground); --normal-border: var(--color-accent); --border-radius: 0px;"
	toastOptions={{
		classes: {
			toast: 'cn-toast font-mono text-ui'
		}
	}}
	{...restProps}
>
	{#snippet loadingIcon()}
		<Loader2Icon class="size-4 animate-spin" />
	{/snippet}
	{#snippet successIcon()}
		<span aria-hidden="true" class="grid size-5 place-items-center bg-grey-400 text-black">
			<svg viewBox="0 0 16 16" class="size-3" fill="none" stroke="currentColor"
				><path d="M3 8.5l3 3 7-7" stroke-width="1.25" stroke-linecap="square" /></svg
			>
		</span>
	{/snippet}
	{#snippet errorIcon()}
		<span aria-hidden="true" class="grid size-5 place-items-center bg-primary-deep text-white"
			>×</span
		>
	{/snippet}
	{#snippet infoIcon()}
		<span aria-hidden="true" class="grid size-5 place-items-center bg-border">→</span>
	{/snippet}
	{#snippet warningIcon()}
		<span aria-hidden="true" class="grid size-5 place-items-center bg-grey-600 text-white">↓</span>
	{/snippet}
</Sonner>
