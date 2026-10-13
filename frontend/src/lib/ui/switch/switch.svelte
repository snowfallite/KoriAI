<script lang="ts">
	import { Switch as SwitchPrimitive } from 'bits-ui';
	import { cn, type WithoutChildrenOrChild } from '$lib/utils/cn.js';

	let {
		ref = $bindable(null),
		class: className,
		checked = $bindable(false),
		size = 'default',
		...restProps
	}: WithoutChildrenOrChild<SwitchPrimitive.RootProps> & {
		size?: 'sm' | 'default';
	} = $props();
</script>

<SwitchPrimitive.Root
	bind:ref
	bind:checked
	data-slot="switch"
	data-size={size}
	class={cn(
		'peer group/switch relative inline-flex shrink-0 items-center rounded-none border p-0.5 transition-colors outline-none after:absolute after:-inset-x-3 after:-inset-y-2 aria-invalid:border-destructive data-[size=default]:h-[22px] data-[size=default]:w-10 data-[size=sm]:h-4 data-[size=sm]:w-7 data-checked:border-foreground data-checked:bg-foreground data-unchecked:border-input data-unchecked:bg-transparent data-disabled:cursor-not-allowed data-disabled:opacity-50',
		className
	)}
	{...restProps}
>
	<SwitchPrimitive.Thumb
		data-slot="switch-thumb"
		class={cn(
			'pointer-events-none block rounded-none ring-0 transition-transform group-data-[size=default]/switch:size-4 group-data-[size=sm]/switch:size-2.5 data-checked:bg-background group-data-[size=default]/switch:data-checked:translate-x-[18px] group-data-[size=sm]/switch:data-checked:translate-x-3 data-unchecked:translate-x-0 data-unchecked:bg-input',
			'rtl:data-[state=checked]:translate-x-[calc(-100%)]'
		)}
	/>
</SwitchPrimitive.Root>
