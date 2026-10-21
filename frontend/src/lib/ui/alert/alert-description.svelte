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
	data-slot="alert-description"
	class={cn(
		'col-start-1 row-start-2 self-start pt-3 pr-4 pb-3 pl-3.5 text-pretty text-muted-foreground group-has-[>[data-slot=alert-title]]/alert:pt-0 [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-foreground [&_p:not(:last-child)]:mb-2',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</div>
