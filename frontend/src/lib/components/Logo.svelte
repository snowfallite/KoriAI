<script lang="ts" module>
	type Size = 'sm' | 'md' | 'lg';

	// 氷 (U+6C37) of Noto Serif JP (SIL Open Font License 1.1) in font units, y up: the seal draws
	// the mark as a path, so it needs no font and looks the same everywhere.
	const GLYPH =
		'M530 800V22Q530 -5 523 -26Q516 -47 492.5 -60Q469 -73 418 -78Q416 -62 410.5 -49Q405 -36 393 -28Q380 -19 357.5 -13Q335 -7 297 -2V14Q297 14 315 12.5Q333 11 358.5 9.5Q384 8 406.5 7Q429 6 438 6Q453 6 458.5 11Q464 16 464 28V838L565 827Q564 817 556.5 810Q549 803 530 800ZM43 511H349V482H52ZM320 511H310L352 552L425 487Q414 476 384 474Q360 385 317 298Q274 211 206.5 136.5Q139 62 41 7L31 21Q111 80 169 159Q227 238 264.5 328Q302 418 320 511ZM530 690Q555 567 600 469.5Q645 372 704 298.5Q763 225 830 170.5Q897 116 966 77L962 67Q941 65 924.5 50Q908 35 899 11Q832 61 773 123Q714 185 664.5 265Q615 345 578 448.5Q541 552 517 684ZM845 674 936 618Q931 611 923 609Q915 607 898 611Q866 579 821 540Q776 501 724.5 463Q673 425 620 393L609 406Q652 445 697.5 493Q743 541 781.5 589Q820 637 845 674ZM170 779Q234 761 274.5 739Q315 717 337.5 693Q360 669 366.5 647.5Q373 626 367 611.5Q361 597 347.5 593Q334 589 315 600Q303 629 277.5 660.5Q252 692 221 720.5Q190 749 160 769Z';
	// The centre of the ink, the centre of the ideographic em box as well.
	const CENTER = [498.5, 380] as const;

	/** A seal of v3 (docs/ui-references/kori-v3/README.md): side, inset and width of the white
	 * frame, size of the glyph, all in px; from 64 px a halftone lies on the red. */
	interface Seal {
		side: number;
		inset: number;
		frame: number;
		glyph: number;
	}
	const SEAL: Record<'24' | '28' | '32' | '64' | '112', Seal> = {
		24: { side: 24, inset: 2, frame: 1, glyph: 14 },
		28: { side: 28, inset: 3, frame: 1, glyph: 16 },
		32: { side: 32, inset: 3, frame: 1, glyph: 19 },
		64: { side: 64, inset: 5, frame: 2, glyph: 38 },
		112: { side: 112, inset: 9, frame: 2, glyph: 68 }
	};

	// The seal and the name side by side; under 768 px a step smaller (seal 22 or 24).
	const COMPACT: Record<Size, { seal: Seal; box: string; text: string; gap: string }> = {
		sm: {
			seal: SEAL[24],
			box: 'size-[22px] md:size-6',
			text: 'text-base/5 md:text-lg/[22px]',
			gap: 'gap-2 md:gap-[9px]'
		},
		md: {
			seal: SEAL[28],
			box: 'size-6 md:size-7',
			text: 'text-xl/6 md:text-[22px]/[26px]',
			gap: 'gap-[9px] md:gap-2.5'
		},
		lg: { seal: SEAL[32], box: 'size-8', text: 'text-[28px]/8', gap: 'gap-3' }
	};
	const SIGN: Record<Size, { seal: Seal; box: string }> = {
		sm: { seal: SEAL[24], box: 'size-6' },
		md: { seal: SEAL[64], box: 'size-16' },
		lg: { seal: SEAL[112], box: 'size-28' }
	};
	// K Ō R I: 44 px on the desktop, 32 on a phone; the kana sit on the gaps between letters.
	const SPACED: Record<Size, { letters: string; kana: string }> = {
		sm: { letters: 'text-[32px]/8', kana: 'mt-2 text-[10px]/3' },
		md: { letters: 'text-[32px]/8 md:text-[44px]/[44px]', kana: 'mt-2 text-[10px]/3 md:mt-2.5 md:text-[11px]/3' },
		lg: { letters: 'text-[64px]/[64px]', kana: 'mt-3 text-sm/4' }
	};
	const LETTERS = ['K', 'Ō', 'R', 'I'];
	const KANA = ['こ', 'お', 'り'];
</script>

<script lang="ts">
	let {
		variant = 'compact',
		size = 'md'
	}: { variant?: 'compact' | 'spaced' | 'sign'; size?: Size } = $props();

	const uid = $props.id();
</script>

<!-- The seal 氷: a red-deep square, a white frame inside, the white glyph (tech.md §13.2). It is
     decor: the name «Kōri» comes from the text next to it or from the label of the sign. -->
{#snippet seal({ side, inset, frame, glyph }: Seal, box: string)}
	{@const scale = glyph / 1000}
	<svg
		data-slot="logo-seal"
		aria-hidden="true"
		viewBox="0 0 {side} {side}"
		class="shrink-0 {box}"
		focusable="false"
	>
		<rect width={side} height={side} class="fill-primary-deep" />
		{#if side >= 64}
			<defs>
				<pattern id="{uid}-dots" width="4" height="4" patternUnits="userSpaceOnUse">
					<circle cx="2" cy="2" r="1.1" fill="#000000" fill-opacity="0.18" />
				</pattern>
			</defs>
			<rect width={side} height={side} fill="url(#{uid}-dots)" />
		{/if}
		<rect
			x={inset + frame / 2}
			y={inset + frame / 2}
			width={side - 2 * inset - frame}
			height={side - 2 * inset - frame}
			fill="none"
			class="stroke-white"
			stroke-width={frame}
			vector-effect="non-scaling-stroke"
		/>
		<path
			d={GLYPH}
			class="fill-white"
			transform="translate({side / 2} {side / 2}) scale({scale} {-scale}) translate({-CENTER[0]} {-CENTER[1]})"
		/>
	</svg>
{/snippet}

{#if variant === 'spaced'}
	<span
		role="img"
		aria-label="Kōri"
		class="inline-grid w-max grid-cols-[repeat(7,auto)] leading-none {SPACED[size].letters}"
	>
		{#each LETTERS as letter, i (letter)}
			{#if i > 0}<span aria-hidden="true" class="w-[0.6em]"></span>{/if}
			<span aria-hidden="true">{letter}</span>
		{/each}
		{#each KANA as kana (kana)}
			<span aria-hidden="true"></span>
			<span
				lang="ja"
				aria-hidden="true"
				class="text-center font-sans font-light text-muted-foreground {SPACED[size].kana}"
				>{kana}</span
			>
		{/each}
		<span aria-hidden="true"></span>
	</span>
{:else if variant === 'sign'}
	<span role="img" aria-label="Kōri" class="inline-flex">
		{@render seal(SIGN[size].seal, SIGN[size].box)}
	</span>
{:else}
	{@const compact = COMPACT[size]}
	<span class="inline-flex items-center tracking-[-0.01em] {compact.gap} {compact.text}">
		{@render seal(compact.seal, compact.box)}
		<span>Kōri</span>
	</span>
{/if}
