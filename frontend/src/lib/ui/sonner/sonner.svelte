<script lang="ts">
	import { mode } from 'mode-watcher';
	import { Toaster as Sonner, type ToasterProps as SonnerProps } from 'svelte-sonner';

	let { ...restProps }: SonnerProps = $props();
</script>

<!-- Toasts speak like the notifications of v4: a row on the accent, the kind in a 2 px bar on the
     left (the ink color for a note, red-deep for an error, grey-600 for a warning, grey-400 for a
     success), no icon and no shadow. The sonner styles sit outside the layers, so the classes
     here are important. -->
<Sonner
	theme={mode.current}
	class="toaster group"
	style="--normal-bg: var(--color-accent); --normal-text: var(--color-foreground); --normal-border: var(--color-foreground); --border-radius: 0px;"
	toastOptions={{
		classes: {
			toast: 'cn-toast font-mono text-ui shadow-none! border-0! border-l-2! py-3! pr-4! pl-3.5!',
			title: 'font-normal!',
			icon: 'hidden!',
			error: 'border-l-primary-deep!',
			warning: 'border-l-grey-600!',
			success: 'border-l-grey-400!'
		}
	}}
	{...restProps}
/>
