<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import type { Suggestion } from '../logic';

	let { suggestions, onPick }: { suggestions: Suggestion[]; onPick: (question: string) => void } =
		$props();

	// The geometry of kori-v4 (chat-start): a column of 820 px, a node of 36 px every 56 px, as
	// wide as its words in the mono face (8.4 px a character at 14 px) plus a source cell of 96 px
	// and 16 px on each side, at least 400 px, flush right.
	const WIDTH = 820;
	const TOP = 40;
	const STEP = 56;
	const NODE = 36;
	const GHOSTS = [260, 170, 90];

	const nodes = $derived(
		suggestions.map((suggestion, n) => {
			const width = Math.min(
				WIDTH,
				Math.max(400, Math.round(suggestion.question.length * 8.4) + 128)
			);
			return { ...suggestion, n, width, left: WIDTH - width, top: TOP + STEP * n };
		})
	);
	const height = $derived(TOP + STEP * Math.max(0, suggestions.length - 1) + NODE + 4);
	/** The lit path: the recommended one, or the node under the pointer or the focus. */
	let hot = $state(0);
</script>

<!-- The fan of a new chat (tech.md §13.3, kori-v4): hairline rays from the corner of the field to
     the questions and the data that answer them; red only on the recommended or pointed path.
     A narrow column gets a plain list. A pick fills the field and sends nothing (F-03 AC 10). -->
<div class="@container">
	<div class="relative hidden w-full @min-[820px]:block" style="height: {height}px">
		<svg
			aria-hidden="true"
			width={WIDTH}
			{height}
			viewBox="0 0 {WIDTH} {height}"
			class="absolute top-0 left-0 overflow-visible"
		>
			<defs>
				<linearGradient id="fan-ray" x1="0" y1="0" x2="1" y2="0">
					<stop offset="0" class="[stop-color:var(--grey-600)]" />
					<stop offset="1" class="[stop-color:var(--border)]" />
				</linearGradient>
				<linearGradient id="fan-hot" x1="0" y1="0" x2="1" y2="0">
					<stop offset="0" class="[stop-color:var(--primary)]" />
					<stop offset="1" class="[stop-color:var(--primary)] [stop-opacity:0.3]" />
				</linearGradient>
				<linearGradient id="fan-ghost" x1="0" y1="0" x2="1" y2="0">
					<stop offset="0" class="[stop-color:var(--border)]" />
					<stop offset="1" class="[stop-color:var(--border)] [stop-opacity:0]" />
				</linearGradient>
			</defs>
			{#each GHOSTS as x, n (x)}
				<path
					pathLength="1"
					d="M0 0L{x} {height}"
					fill="none"
					stroke="url(#fan-ghost)"
					class="animate-ki-draw [stroke-dasharray:1]"
					style="animation-delay: {0.05 + 0.07 * n}s"
				/>
			{/each}
			{#each nodes as node (node.n)}
				<path
					pathLength="1"
					d="M0 0L{node.left - 2} {node.top + NODE / 2}"
					fill="none"
					stroke={node.n === hot ? 'url(#fan-hot)' : 'url(#fan-ray)'}
					stroke-width={node.n === hot ? 1.25 : 1}
					class="animate-ki-draw [stroke-dasharray:1]"
					style="animation-delay: {0.15 + 0.08 * node.n}s"
				/>
				<rect
					x={node.left - 5}
					y={node.top + NODE / 2 - 1.5}
					width="3"
					height="3"
					class={node.n === hot ? 'fill-primary' : 'fill-grey-600'}
				/>
			{/each}
			<rect x="-3" y="-3" width="6" height="6" class="fill-primary" />
		</svg>
		<ul aria-label="Примеры вопросов">
			{#each nodes as node (node.n)}
				<li>
					<button
						type="button"
						class={cn(
							'absolute flex h-9 animate-ki-pop border bg-background text-left text-[14px]/4 transition-colors hover:border-foreground hover:text-foreground focus-visible:border-foreground',
							node.n === hot
								? 'border-grey-600 text-foreground'
								: 'border-border text-foreground/85'
						)}
						style="left: {node.left}px; top: {node.top}px; width: {node.width}px; animation-delay: {0.55 +
							0.08 * node.n}s"
						onpointerenter={() => (hot = node.n)}
						onpointerleave={() => (hot = 0)}
						onfocus={() => (hot = node.n)}
						onblur={() => (hot = 0)}
						onclick={() => onPick(node.question)}
					>
						<span
							class={cn(
								'flex w-24 shrink-0 items-center justify-center border-r bg-accent text-caption',
								node.n === hot ? 'text-primary' : 'text-muted-foreground'
							)}>{node.source}</span
						>
						<span class="flex min-w-0 flex-1 items-center truncate px-4">{node.question}</span>
					</button>
				</li>
			{/each}
		</ul>
	</div>
	<ul aria-label="Примеры вопросов" class="mt-6 flex flex-col gap-2 @min-[820px]:hidden">
		{#each suggestions as suggestion (suggestion.question)}
			<li>
				<button
					type="button"
					class="flex min-h-11 w-full flex-col items-start gap-1 border bg-background px-4 py-2.5 text-left text-[14px]/5 hover:border-foreground"
					onclick={() => onPick(suggestion.question)}
				>
					<span class="text-caption text-muted-foreground">{suggestion.source}</span>
					{suggestion.question}
				</button>
			</li>
		{/each}
	</ul>
</div>
