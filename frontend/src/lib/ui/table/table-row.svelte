<script lang="ts">
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLTableRowElement>> = $props();
</script>

<tr
	bind:this={ref}
	data-slot="table-row"
	class={cn(
		// The hover of a row is the ink at 5 % (#0D0D0D at night, kori-v4); a chosen row takes the accent.
		'border-b border-line-faint transition-colors hover:bg-foreground/5 has-aria-expanded:bg-accent data-[state=selected]:bg-accent',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</tr>
