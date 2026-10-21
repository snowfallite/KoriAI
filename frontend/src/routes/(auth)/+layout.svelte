<script lang="ts">
	import { page } from '$app/state';
	import Logo from '$lib/components/Logo.svelte';
	import { CANDLES, candleShapes } from './logic';

	let { children } = $props();

	const uid = $props.id();
	const shapes = CANDLES.map(candleShapes);
	// The registration form is longer: a smaller name and less air above it (kori-v4).
	const register = $derived(page.url.pathname.startsWith('/register'));

	// The glow over the peak of the chart and its echo in the lower corner, with the colors of
	// html/login.html through the tokens: --primary 95 %, --primary-deep 60 %, --red-800 40 %, then
	// --pink 30 %. A phone gets a wider, flatter ellipse over the top of its screen.
	const GLOW =
		'bg-[image:radial-gradient(ellipse_90%_45%_at_92%_0%,color-mix(in_srgb,var(--primary)_95%,transparent)_0%,color-mix(in_srgb,var(--primary-deep)_60%,transparent)_28%,color-mix(in_srgb,var(--red-800)_40%,transparent)_52%,transparent_78%),radial-gradient(ellipse_70%_30%_at_0%_62%,color-mix(in_srgb,var(--pink)_22%,transparent)_0%,transparent_70%)] md:bg-[image:radial-gradient(ellipse_58%_64%_at_84%_4%,color-mix(in_srgb,var(--primary)_95%,transparent)_0%,color-mix(in_srgb,var(--primary-deep)_60%,transparent)_26%,color-mix(in_srgb,var(--red-800)_40%,transparent)_50%,transparent_76%),radial-gradient(ellipse_42%_46%_at_6%_100%,color-mix(in_srgb,var(--pink)_30%,transparent)_0%,transparent_70%)]';
	// Hairlines of the ink at 5 % every 56 px, every 40 px on a phone.
	const GRID =
		'bg-[image:repeating-linear-gradient(0deg,color-mix(in_srgb,var(--foreground)_5%,transparent)_0px,color-mix(in_srgb,var(--foreground)_5%,transparent)_1px,transparent_1px,transparent_40px)] md:bg-[image:repeating-linear-gradient(0deg,color-mix(in_srgb,var(--foreground)_5%,transparent)_0px,color-mix(in_srgb,var(--foreground)_5%,transparent)_1px,transparent_1px,transparent_56px)]';
</script>

<!-- The scene «свет над графиком» (tech.md §13.3, docs/ui-references/kori-v4): black, a red glow
     over the peak of a chart of Japanese candles, a hairline grid and grain, the same in both
     themes. It is decor: the page reads the name and the form only. -->
<div
	class="theme-night relative isolate flex min-h-svh flex-col overflow-hidden bg-background text-foreground"
>
	<div aria-hidden="true" class="absolute inset-0 -z-10 {GLOW}"></div>
	<div aria-hidden="true" class="absolute inset-0 -z-10 {GRID}"></div>
	<!-- Hollow white rises, red falls sinking into --red-900, wicks outside the bodies; on a
	     phone the chart keeps the top 520 px and its middle. -->
	<svg
		aria-hidden="true"
		viewBox="0 0 1440 900"
		preserveAspectRatio="xMidYMid slice"
		class="absolute inset-x-0 top-0 -z-10 h-[520px] w-full md:h-full"
	>
		<defs>
			<linearGradient id="{uid}-fall" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0" class="[stop-color:var(--primary)]" />
				<stop offset="1" class="[stop-color:var(--red-900)]" />
			</linearGradient>
		</defs>
		<g class="stroke-foreground" stroke-opacity="0.35">
			{#each shapes as { wicks }, i (i)}
				{#each wicks as wick (wick.y1)}
					<line
						x1={wick.x}
						y1={wick.y1}
						x2={wick.x}
						y2={wick.y2}
						vector-effect="non-scaling-stroke"
					/>
				{/each}
			{/each}
		</g>
		<g fill="url(#{uid}-fall)">
			{#each shapes as { rise, body }, i (i)}
				{#if !rise}
					<rect x={body.x} y={body.y} width={body.width} height={body.height} />
				{/if}
			{/each}
		</g>
		<g fill="none" class="stroke-foreground" stroke-opacity="0.85">
			{#each shapes as { rise, body }, i (i)}
				{#if rise}
					<rect
						x={body.x}
						y={body.y}
						width={body.width}
						height={body.height}
						vector-effect="non-scaling-stroke"
					/>
				{/if}
			{/each}
		</g>
	</svg>
	<svg aria-hidden="true" class="absolute inset-0 -z-10 size-full opacity-[0.07]">
		<filter id="{uid}-grain">
			<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
			<feColorMatrix type="saturate" values="0" />
		</filter>
		<rect width="100%" height="100%" filter="url(#{uid}-grain)" />
	</svg>

	<!-- The spaced name over the form; on a phone the name stays on top and the form at the
	     bottom, 12 px from the edges. -->
	<main
		class="flex flex-1 flex-col items-center px-3 pt-11 pb-3 md:justify-center md:px-4 {register
			? 'md:py-8'
			: 'md:py-12'}"
	>
		<div class={register ? 'md:mb-8' : 'md:mb-11'}>
			<Logo variant="spaced" size={register ? 'md' : 'lg'} />
		</div>
		<div aria-hidden="true" class="min-h-8 flex-1 md:hidden"></div>
		{@render children()}
	</main>
</div>
