<script lang="ts" module>
	type Size = 'sm' | 'md' | 'lg';

	// The mark of Kōri v4 (docs/ui-references/kori-v4/README.md, «Знак»): the name set in
	// JetBrains Mono, no seal. Compact is 24/28 in the headers of the app and of the error page.
	const COMPACT: Record<Size, string> = {
		sm: 'text-lg/6',
		md: 'text-2xl/7',
		lg: 'text-[40px]/[44px]'
	};
	// K Ō R I over the sign-in form: 128 px on the login page (lg), 96 on the registration (md),
	// 52 on a phone; the kana sit in the gaps between the letters.
	const SPACED: Record<Size, { letters: string; kana: string }> = {
		sm: { letters: 'text-[52px]/[52px]', kana: 'mt-2 text-[13px]/4' },
		md: {
			letters: 'text-[52px]/[52px] md:text-[96px]/[96px]',
			kana: 'mt-2 text-[13px]/4 md:mt-3 md:text-[18px]/[22px]'
		},
		lg: {
			letters: 'text-[52px]/[52px] md:text-[128px]/[128px]',
			kana: 'mt-2 text-[13px]/4 md:mt-3.5 md:text-[22px]/[26px]'
		}
	};
	// The sign «Kō» on a red-deep square, as the favicon draws it.
	const SIGN: Record<Size, string> = {
		sm: 'size-6 text-[11px]',
		md: 'size-8 text-[14px]',
		lg: 'size-16 text-[28px]'
	};
	const LETTERS = ['K', 'Ō', 'R', 'I'];
	const KANA = ['こ', 'お', 'り'];
</script>

<script lang="ts">
	let {
		variant = 'compact',
		size = 'md'
	}: { variant?: 'compact' | 'spaced' | 'sign'; size?: Size } = $props();
</script>

<!-- tech.md §13.2: the name reads «Kōri» in every form; the spaced letters, the kana and the sign
     are drawn for the eye and stay silent. -->
{#if variant === 'spaced'}
	<span
		role="img"
		aria-label="Kōri"
		class="inline-grid w-max grid-cols-[repeat(7,auto)] font-light {SPACED[size].letters}"
	>
		{#each LETTERS as letter, i (letter)}
			{#if i > 0}<span aria-hidden="true" class="w-[0.6em]"></span>{/if}
			<!-- The letters fade downwards: the ink color to 46 % of the line, then towards 28 %. The
			     fill reaches 0.2 em above the line, or the macron of Ō would fall outside it, so the
			     46 % of the line stand at 55 % of the fill. -->
			<span
				aria-hidden="true"
				class="-mt-[0.2em] bg-linear-to-b from-foreground from-0% via-foreground via-55% to-foreground/28 to-100% bg-clip-text pt-[0.2em] text-transparent"
				>{letter}</span
			>
		{/each}
		{#each KANA as kana (kana)}
			<span aria-hidden="true"></span>
			<span
				lang="ja"
				aria-hidden="true"
				class="text-center font-light text-primary {SPACED[size].kana}">{kana}</span
			>
		{/each}
		<span aria-hidden="true"></span>
	</span>
{:else if variant === 'sign'}
	<span
		role="img"
		aria-label="Kōri"
		class="inline-grid shrink-0 place-items-center bg-primary-deep tracking-[-0.02em] text-primary-deep-foreground {SIGN[
			size
		]}"
	>
		<span aria-hidden="true">Kō</span>
	</span>
{:else}
	<span class="inline-block tracking-[-0.02em] {COMPACT[size]}">Kōri</span>
{/if}
