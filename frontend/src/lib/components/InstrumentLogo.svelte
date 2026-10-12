<script lang="ts">
	import * as Avatar from '$lib/ui/avatar';
	import { cn } from '$lib/utils/cn';

	type Size = 20 | 24 | 32 | 48;

	// The brand color stays in the props of tech.md §13.2, but it paints nothing: the tile is
	// neutral (docs/ui-references/kori-v3).
	let {
		src,
		name,
		size = 24
	}: { src: string | null; name: string; color?: string | null; size?: Size } = $props();

	// A square tile and initials to scale: 11 px on the 32 px tile of the positions.
	const TILE: Record<Size, string> = { 20: 'size-5', 24: 'size-6', 32: 'size-8', 48: 'size-12' };
	const INITIALS: Record<Size, string> = {
		20: 'text-[8px]',
		24: 'text-[9px]',
		32: 'text-[11px]',
		48: 'text-[14px]'
	};

	const initials = $derived.by(() => {
		const words = name.trim().split(/\s+/);
		const letters =
			words.length > 1
				? (words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')
				: (words[0] ?? '').slice(0, 2);
		return letters.toUpperCase();
	});
</script>

<Avatar.Root class={cn(TILE[size], 'rounded-none after:hidden')}>
	{#if src}
		<Avatar.Image {src} alt={name} class="rounded-none" />
	{/if}
	<!-- Without a logo the initials stand in white on the grey-900 tile, in both themes. -->
	<Avatar.Fallback class={cn('rounded-none bg-grey-900 text-white', INITIALS[size])}>
		{initials}
	</Avatar.Fallback>
</Avatar.Root>
