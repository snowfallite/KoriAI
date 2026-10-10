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
		'border-b border-line-faint transition-colors hover:bg-accent has-aria-expanded:bg-accent data-[state=selected]:bg-accent',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</tr>
