<script lang="ts">
	type Size = 'sm' | 'md' | 'lg';

	let {
		variant = 'compact',
		size = 'md'
	}: { variant?: 'compact' | 'spaced' | 'sign'; size?: Size } = $props();

	const COMPACT: Record<Size, string> = { sm: 'text-base', md: 'text-xl', lg: 'text-6xl' };
	const SPACED: Record<Size, string> = { sm: 'text-3xl', md: 'text-6xl', lg: 'text-8xl' };
	const SIGN: Record<Size, string> = {
		sm: 'size-6 border-2 text-[10px]',
		md: 'size-10 border-[3px] text-base',
		lg: 'size-16 border-4 text-2xl'
	};
	const LETTERS = ['K', 'Ō', 'R', 'I'];
	// こおり sits under Ō, R and I, as きおく sits under Ï, O and the second K of Kïoku.
	const KANA = ['', 'こ', 'お', 'り'];
</script>

<!-- The Kïoku logo in its three forms (tech.md §13.2): live JetBrains Mono, never red letters. -->
{#if variant === 'spaced'}
	<span
		role="img"
		aria-label="Kōri"
		class="inline-grid w-max grid-cols-4 gap-x-[1em] leading-none {SPACED[size]}"
	>
		{#each LETTERS as letter (letter)}
			<span aria-hidden="true">{letter}</span>
		{/each}
		{#each KANA as kana, i (i)}
			<span
				lang="ja"
				aria-hidden="true"
				class="mt-[0.2em] text-center font-sans text-[0.21em] font-light text-muted-foreground"
				>{kana}</span
			>
		{/each}
	</span>
{:else if variant === 'sign'}
	<span
		role="img"
		aria-label="Kōri"
		class="inline-grid place-items-center border-black bg-white leading-none text-black {SIGN[
			size
		]}">Kō</span
	>
{:else}
	<span class="inline-flex items-start gap-1 leading-none {COMPACT[size]}"
		>Kōri<span
			lang="ja"
			aria-hidden="true"
			class="font-serif text-[max(10px,0.22em)] leading-none text-muted-foreground">氷</span
		></span
	>
{/if}
