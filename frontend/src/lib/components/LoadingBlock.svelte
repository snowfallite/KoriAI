<script lang="ts">
	import { Skeleton } from '$lib/ui/skeleton';

	let { rows = 3, variant = 'text' }: { rows?: number; variant?: 'text' | 'table' | 'chart' } =
		$props();
</script>

<div role="status" class="space-y-2">
	<span class="sr-only">Загрузка</span>
	{#if variant === 'chart'}
		<Skeleton class="h-64 w-full" />
	{:else if variant === 'table'}
		<Skeleton class="h-8 w-full" />
		{#each { length: rows }, i (i)}
			<Skeleton class="h-6 w-full opacity-60" />
		{/each}
	{:else}
		{#each { length: rows }, i (i)}
			<Skeleton class={i === rows - 1 ? 'h-3 w-2/3' : 'h-3 w-full'} />
		{/each}
	{/if}
</div>
