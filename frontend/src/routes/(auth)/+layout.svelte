<script lang="ts">
	import { page } from '$app/state';
	import Logo from '$lib/components/Logo.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';

	let { children } = $props();

	// The cover of v3 (docs/ui-references/kori-v3/README.md): arches of stepped blocks standing on
	// the bottom edge and hairline rays to a point low in the centre, on the brand gradient that
	// sinks into the page. The art keeps a 1440 × 900 box and covers the screen.
	const W = 1440;
	const H = 900;
	const ROW = 56;
	const BLOCK = 34;
	const FOCUS = { x: W / 2, y: H - 20 };

	// Ellipses on the bottom edge: half-widths 150 … 750 in steps of 88, 1.55 times as high; one
	// block a row on each side, its left edge rounded to 2 px.
	const blocks: { x: number; y: number }[] = [];
	for (let a = 150; a <= 750; a += 88) {
		const b = a * 1.55;
		for (let y = 0; y < H; y += ROW) {
			const dy = H - (y + ROW / 2);
			if (dy > b) continue;
			const dx = a * Math.sqrt(1 - (dy / b) ** 2);
			for (const x of [W / 2 - dx, W / 2 + dx]) {
				blocks.push({ x: Math.round((x - BLOCK / 2) / 2) * 2, y });
			}
		}
	}

	// 65 rays to the top edge, past both corners, and 10 to each side.
	const rays = [
		...Array.from({ length: 65 }, (_, i) => ({ x: -144 + 27 * i, y: 0 })),
		...Array.from({ length: 10 }, (_, i) => 60 + 70 * i).flatMap((y) => [
			{ x: 0, y },
			{ x: W, y }
		])
	];

	const LOGIN = {
		note: 'Вход для закрытого круга',
		footer: ['Т-Инвестиции · доступ только на чтение', 'Токен хранится зашифрованным']
	};
	const REGISTER = {
		note: 'Регистрация по приглашению',
		footer: ['Пароль от 10 символов · хранится как хеш', 'Т-Инвестиции · доступ только на чтение']
	};
	const meta = $derived(page.url.pathname.startsWith('/register') ? REGISTER : LOGIN);
</script>

<div class="relative isolate flex min-h-svh flex-col overflow-hidden">
	<!-- Decor only. On a phone the cover keeps the top 560 px and the panel stands under it. -->
	<div
		aria-hidden="true"
		class="absolute inset-x-0 top-0 -z-10 h-[560px] ki-tile md:inset-y-0 md:h-auto dark:ki-hero"
	>
		<svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" class="size-full">
			<g class="fill-primary">
				{#each blocks as block, i (i)}
					<rect x={block.x} y={block.y} width={BLOCK} height={ROW} />
				{/each}
			</g>
			<g class="stroke-background" stroke-opacity="0.2">
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
		</svg>
		<div
			class="absolute inset-0 bg-linear-to-b from-transparent from-50% to-background to-88%"
		></div>
	</div>

	<!-- The meta line in black ink on the cover, in either theme. -->
	<header
		class="theme-day relative flex flex-wrap items-center justify-between gap-x-8 gap-y-2 bg-transparent px-4 py-3 text-caps tracking-[0.04em] text-foreground uppercase md:px-12 md:py-4"
	>
		<span>
			<span class="md:hidden">Kōri</span>
			<span class="hidden md:inline">Kōri · аналитик портфеля</span>
		</span>
		<span class="hidden md:inline">{meta.note}</span>
		<ThemeToggle />
	</header>

	<div class="flex flex-1 flex-col">
		<div class="flex flex-1 items-end justify-center pb-7 md:hidden">
			<Logo variant="spaced" size="sm" />
		</div>
		<main class="flex justify-center px-3 pb-3 md:flex-1 md:items-center md:px-4 md:pt-6 md:pb-0">
			{@render children()}
		</main>
		<div class="hidden justify-center px-4 pt-12 pb-2 md:flex">
			<Logo variant="spaced" />
		</div>
		<footer
			class="hidden flex-wrap justify-between gap-x-6 gap-y-2 px-12 pt-4 pb-5 text-caption text-grey-600 uppercase md:flex"
		>
			{#each meta.footer as line (line)}
				<span>{line}</span>
			{/each}
		</footer>
	</div>
</div>
