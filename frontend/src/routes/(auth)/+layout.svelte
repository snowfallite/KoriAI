<script lang="ts">
	import Logo from '$lib/components/Logo.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';

	let { children } = $props();

	// The Kïoku hero (docs/ui-references/template/components/Hero): nested arches of stepped
	// blocks and rays converging low in the centre, on the brand gradient that sinks into the page.
	const W = 1184;
	const H = 560;
	const ROW = 50;
	const BW = 30;
	const SPRING = H * 0.42; // below it the arches stand on straight legs
	const FOCUS = { x: W / 2, y: H * 0.9 };
	const RAYS = 56;

	const rays = [
		...Array.from({ length: RAYS + 1 }, (_, i) => ({ x: -W * 0.15 + (i / RAYS) * W * 1.3, y: 0 })),
		...[1, 2, 3, 4, 5, 6].flatMap((j) => [
			{ x: 0, y: (j * H) / 9 },
			{ x: W, y: (j * H) / 9 }
		])
	];

	const blocks: { x: number; y: number }[] = [];
	for (let r = 96; r <= 640; r += 76) {
		for (let y = ROW / 2; y < H; y += ROW) {
			const dy = SPRING - y;
			if (dy > 0 && r <= dy) continue;
			const dx = dy > 0 ? Math.sqrt(r * r - dy * dy) : r;
			for (const x of [W / 2 - dx, W / 2 + dx]) {
				const left = Math.round((x - BW / 2) / 2) * 2;
				if (left >= -BW && left <= W) blocks.push({ x: left, y: y - ROW / 2 });
			}
		}
	}
</script>

<div class="flex min-h-svh flex-col">
	<header class="flex h-12 shrink-0 items-center justify-end px-4"><ThemeToggle /></header>

	<div class="px-4 md:px-12">
		<!-- Decor only. The field fades into the page: black at night, white by day. -->
		<div
			class="relative mx-auto aspect-[1184/560] max-h-[38svh] w-full max-w-[1184px] overflow-hidden ki-tile dark:ki-hero"
			aria-hidden="true"
		>
			<svg
				viewBox="0 0 {W} {H}"
				preserveAspectRatio="xMidYMin slice"
				class="absolute inset-0 size-full"
			>
				<g class="stroke-primary">
					{#each rays as ray, i (i)}
						<line
							x1={FOCUS.x}
							y1={FOCUS.y}
							x2={ray.x}
							y2={ray.y}
							vector-effect="non-scaling-stroke"
						/>
					{/each}
				</g>
				<g class="fill-primary">
					{#each blocks as block, i (i)}
						<rect x={block.x} y={block.y} width={BW} height={ROW} />
					{/each}
				</g>
			</svg>
			<div
				class="absolute inset-0 bg-linear-to-b from-transparent from-50% to-background to-[97%]"
			></div>
		</div>
	</div>

	<!-- The logo grows out of the fade, as on the Kïoku hero. -->
	<div class="relative -mt-5 flex justify-center md:-mt-9">
		<span class="md:hidden"><Logo variant="spaced" size="sm" /></span>
		<span class="hidden md:inline"><Logo variant="spaced" /></span>
	</div>

	<main class="mx-auto w-full max-w-sm flex-1 px-4 pt-10 pb-16">
		{@render children()}
	</main>
</div>
