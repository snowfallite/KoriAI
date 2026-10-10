<script lang="ts">
	import { RadioGroup as RadioGroupPrimitive } from 'bits-ui';
	import { cn, type WithoutChildrenOrChild } from '$lib/utils/cn.js';

	let {
		ref = $bindable(null),
		class: className,
		...restProps
	}: WithoutChildrenOrChild<RadioGroupPrimitive.ItemProps> = $props();
</script>

<RadioGroupPrimitive.Item
	bind:ref
	data-slot="radio-group-item"
	class={cn(
		'group/radio-group-item peer relative flex aspect-square size-3 shrink-0 rounded-none border border-input outline-none after:absolute after:-inset-x-3 after:-inset-y-2 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive data-checked:border-current data-checked:bg-current',
		className
	)}
	{...restProps}
>
	<!-- The fill of the square is the mark: nothing goes inside. -->
	{#snippet children()}{/snippet}
</RadioGroupPrimitive.Item>
