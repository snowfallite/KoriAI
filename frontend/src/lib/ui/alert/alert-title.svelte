<script lang="ts">
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLDivElement>> = $props();
</script>

<div
	bind:this={ref}
	data-slot="alert-title"
	class={cn(
		'col-start-1 row-start-1 self-end pt-3 pr-4 pb-3 pl-3.5 group-has-[>[data-slot=alert-description]]/alert:pb-0.5 [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-foreground',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</div>
