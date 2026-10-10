<script lang="ts" module>
	import { type VariantProps, tv } from 'tailwind-variants';

	// A notification of v3: a row on the accent, a glyph cell on the left (× error, ↓ downgrade,
	// a tick when done, → for a note), the text, an action in caps on the right. The glyph is the
	// first child <span data-slot="alert-glyph" aria-hidden="true">; its color comes from the variant
	// or from the class of the span.
	export const alertVariants = tv({
		base: 'group/alert relative grid min-h-11 w-full grid-cols-[auto_minmax(0,1fr)_auto] rounded-none bg-accent text-left text-ui text-foreground *:data-[slot=alert-glyph]:col-start-1 *:data-[slot=alert-glyph]:row-span-2 *:data-[slot=alert-glyph]:row-start-1 *:data-[slot=alert-glyph]:grid *:data-[slot=alert-glyph]:min-h-11 *:data-[slot=alert-glyph]:w-11 *:data-[slot=alert-glyph]:place-items-center *:data-[slot=alert-glyph]:text-[15px] *:data-[slot=alert-glyph]:[&>svg]:size-3.5',
		variants: {
			variant: {
				default: '*:data-[slot=alert-glyph]:bg-border *:data-[slot=alert-glyph]:text-foreground',
				destructive:
					'*:data-[slot=alert-glyph]:bg-primary-deep *:data-[slot=alert-glyph]:text-primary-deep-foreground'
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
