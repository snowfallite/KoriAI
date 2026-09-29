<script lang="ts">
	import * as Avatar from '$lib/ui/avatar';
	import { cn } from '$lib/utils/cn';

	type Size = 20 | 24 | 32 | 48;

	let {
		src,
		name,
		color = null,
		size = 24
	}: { src: string | null; name: string; color?: string | null; size?: Size } = $props();

	const SIZE: Record<Size, string> = {
		20: 'size-5 text-[8px]',
		24: 'size-6 text-[9px]',
		32: 'size-8 text-[11px]',
		48: 'size-12 text-sm'
	};

	const initials = $derived.by(() => {
		const words = name.trim().split(/\s+/);
		const letters =
			words.length > 1
				? (words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')
				: (words[0] ?? '').slice(0, 2);
		return letters.toUpperCase();
	});

	const brand = $derived(color && /^#[0-9a-f]{6}$/i.test(color) ? color : null);

	/** Black or white ink, whichever reads better on the brand color (WCAG luminance). */
	function inkOn(hex: string): string {
		const [r, g, b] = [1, 3, 5].map((i) => {
			const c = parseInt(hex.slice(i, i + 2), 16) / 255;
			return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
		}) as [number, number, number];
		return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.179 ? 'text-black' : 'text-white';
	}
</script>

<!-- Square like every Kïoku shape (radius 0, tech.md §13.3). -->
<Avatar.Root class={cn(SIZE[size], 'rounded-none after:rounded-none')}>
	{#if src}
		<Avatar.Image {src} alt={name} class="rounded-none" />
	{/if}
	<Avatar.Fallback
		class={cn('rounded-none font-medium', brand && inkOn(brand))}
		style={brand ? `background-color: ${brand}` : undefined}
	>
		{initials}
	</Avatar.Fallback>
</Avatar.Root>
