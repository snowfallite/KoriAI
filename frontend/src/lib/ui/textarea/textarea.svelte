<script lang="ts">
	import { cn, type WithElementRef, type WithoutChildren } from '$lib/utils/cn.js';
	import type { HTMLTextareaAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		value = $bindable(),
		class: className,
		'data-slot': dataSlot = 'textarea',
		...restProps
	}: WithoutChildren<WithElementRef<HTMLTextareaAttributes>> = $props();
</script>

<textarea
	bind:this={ref}
	data-slot={dataSlot}
	class={cn(
		'flex field-sizing-content min-h-16 w-full rounded-none border border-input bg-transparent px-3 py-2.5 text-base text-foreground transition-colors outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:bg-accent disabled:text-muted-foreground aria-invalid:border-primary-deep aria-invalid:shadow-[inset_0_0_0_1px_var(--primary-deep)] md:text-ui',
		className
	)}
	bind:value
	{...restProps}></textarea>
