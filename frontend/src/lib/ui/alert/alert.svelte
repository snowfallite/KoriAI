<script lang="ts" module>
	import { type VariantProps, tv } from 'tailwind-variants';

	// A notification of v4: a row of 44 px on the accent, the text, an action on the right. The
	// kind shows in a 2 px bar on the left, never in a glyph cell: red-deep for an error, the ink
	// color for a note; a downgrade (border-l-grey-600) or a success (border-l-grey-400) sets its
	// bar with a class.
	export const alertVariants = tv({
		base: 'group/alert relative grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] rounded-none border-l-2 bg-accent text-left text-ui text-foreground',
		variants: {
			variant: {
				default: 'border-l-foreground',
				destructive: 'border-l-primary-deep'
			}
		},
		defaultVariants: {
			variant: 'default'
		}
	});

	export type AlertVariant = VariantProps<typeof alertVariants>['variant'];
</script>

<script lang="ts">
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		class: className,
		variant = 'default',
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLDivElement>> & {
		variant?: AlertVariant;
	} = $props();
</script>

<div
	bind:this={ref}
	data-slot="alert"
	role="alert"
	class={cn(alertVariants({ variant }), className)}
	{...restProps}
>
	{@render children?.()}
</div>
