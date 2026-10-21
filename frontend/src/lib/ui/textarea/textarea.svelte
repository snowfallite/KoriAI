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
		// A field as an input is (tech.md §13.3): the line under it on focus, a fill on a white panel.
		'flex field-sizing-content min-h-16 w-full rounded-none border border-input bg-transparent px-3 py-2.5 text-base text-foreground transition-[color,box-shadow] outline-none placeholder:text-muted-foreground focus:shadow-[inset_0_-2px_0_var(--foreground)] disabled:cursor-not-allowed disabled:bg-accent disabled:text-muted-foreground in-[.theme-day]:border-transparent in-[.theme-day]:bg-muted aria-invalid:border-primary-deep aria-invalid:shadow-[inset_0_-2px_0_var(--primary-deep)] in-[.theme-day]:aria-invalid:border-transparent md:text-ui',
		className
	)}
	bind:value
	{...restProps}></textarea>
