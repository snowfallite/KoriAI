<script lang="ts">
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLInputAttributes, HTMLInputTypeAttribute } from 'svelte/elements';

	type InputType = Exclude<HTMLInputTypeAttribute, 'file'>;

	type Props = WithElementRef<
		Omit<HTMLInputAttributes, 'type'> &
			({ type: 'file'; files?: FileList } | { type?: InputType; files?: undefined })
	>;

	let {
		ref = $bindable(null),
		value = $bindable(),
		type,
		files = $bindable(),
		class: className,
		'data-slot': dataSlot = 'input',
		...restProps
	}: Props = $props();

	// tech.md §13.3: a field shows its focus as a 2 px line under it, an error as a red-deep line.
	// On a white panel (.theme-day) it is a --muted fill without a frame; elsewhere it keeps the
	// frame of the controls.
	const INPUT_CLASS =
		'h-10 w-full min-w-0 rounded-none border border-input bg-transparent px-3 py-1 text-base text-foreground transition-[color,box-shadow] outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-ui file:text-foreground placeholder:text-muted-foreground focus:shadow-[inset_0_-2px_0_var(--foreground)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-accent disabled:text-muted-foreground aria-invalid:border-primary-deep aria-invalid:shadow-[inset_0_-2px_0_var(--primary-deep)] md:text-ui in-[.theme-day]:border-transparent in-[.theme-day]:bg-muted in-[.theme-day]:aria-invalid:border-transparent';
</script>

{#if type === 'file'}
	<input
		bind:this={ref}
		data-slot={dataSlot}
		class={cn(INPUT_CLASS, className)}
		type="file"
		bind:files
		bind:value
		{...restProps}
	/>
{:else}
	<input
		bind:this={ref}
		data-slot={dataSlot}
		class={cn(INPUT_CLASS, className)}
		{type}
		bind:value
		{...restProps}
	/>
{/if}
