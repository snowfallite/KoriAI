<script lang="ts" module>
	// A currency tile shows its code (tech.md §13.2). The props carry the name only, so the code
	// comes from the Russian name of the currency as CLDR spells it: «Доллар США» is USD.
	// A browser without these Intl parts keeps the initials instead of failing the module.
	const CURRENCY =
		typeof Intl.DisplayNames === 'function' && typeof Intl.supportedValuesOf === 'function'
			? new Intl.DisplayNames(['ru'], { type: 'currency' })
			: null;
	const CODES = new Map(
		CURRENCY
			? Intl.supportedValuesOf('currency').map((code) => [CURRENCY.of(code)?.toLowerCase(), code])
			: []
	);

	/** The text of the tile: «ОФЗ» for a federal loan bond, the code of a currency, else the
	 * initials of two words or the first letters of one, up to its hyphen («Т-Технологии»: Т). */
	function tileOf(name: string): string {
		const text = name.trim();
		if (/^ОФЗ(\s|$)/.test(text)) return 'ОФЗ';
		const code = CODES.get(text.toLowerCase());
		if (code) return code;
		const [first = '', second] = text.split(/\s+/);
		const letters = second ? (first[0] ?? '') + (second[0] ?? '') : (first.split('-')[0] ?? '');
		return letters.slice(0, 2).toUpperCase();
	}
</script>

<script lang="ts">
	import * as Avatar from '$lib/ui/avatar';
	import { cn } from '$lib/utils/cn';

	type Size = 20 | 24 | 32 | 48;

	// The brand color stays in the props of tech.md §13.2, but it paints nothing: the tile is
	// neutral (docs/ui-references/kori-v3).
	// eslint-disable-next-line svelte/no-unused-props -- the contract keeps color
	let {
		src,
		name,
		size = 24
	}: {
		src: string | null;
		name: string;
		color?: string | null;
		size?: Size;
	} = $props();

	// A square tile and initials to scale: 11 px on the 32 px tile of the positions.
	const TILE: Record<Size, string> = { 20: 'size-5', 24: 'size-6', 32: 'size-8', 48: 'size-12' };
	const INITIALS: Record<Size, string> = {
		20: 'text-[8px]',
		24: 'text-[9px]',
		32: 'text-[11px]',
		48: 'text-[14px]'
	};

	const initials = $derived(tileOf(name));
</script>

<Avatar.Root class={cn(TILE[size], 'rounded-none after:hidden')}>
	{#if src}
		<Avatar.Image {src} alt={name} class="rounded-none" />
	{/if}
	<!-- Without a logo the tile text stands in white on the grey-900 tile, in both themes. -->
	<Avatar.Fallback class={cn('rounded-none bg-grey-900 text-white', INITIALS[size])}>
		{initials}
	</Avatar.Fallback>
</Avatar.Root>
