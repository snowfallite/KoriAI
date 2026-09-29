<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/ui/button';

	let { text, label = 'Копировать' }: { text: string; label?: string } = $props();

	let copied = $state(false);

	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			// The browser refuses the clipboard outside a secure context or without permission.
			toast.error('Не удалось скопировать');
			return;
		}
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
</script>

<Button variant="ghost" size="icon-sm" aria-label={label} title={label} onclick={copy}>
	{#if copied}
		<Check />
	{:else}
		<Copy />
	{/if}
</Button>
