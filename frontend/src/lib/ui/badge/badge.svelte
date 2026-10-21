<script lang="ts" module>
	import { type VariantProps, tv } from 'tailwind-variants';

	export const badgeVariants = tv({
		base: 'h-6 gap-1 rounded-none border border-transparent px-2 text-caption transition-colors has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&>svg]:size-3! group/badge inline-flex w-fit shrink-0 items-center justify-center overflow-hidden whitespace-nowrap aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none',
		variants: {
			variant: {
				default: 'bg-foreground text-background [a]:hover:bg-grey-200',
				// Kïoku tags: the category plate, the red-deep counter plate, the ink frame.
				secondary: 'bg-grey-300 text-black [a]:hover:bg-grey-200',
				destructive: 'border-primary-deep text-negative [a]:hover:bg-accent',
				outline:
					'border-foreground text-foreground [a]:hover:bg-foreground [a]:hover:text-background',
				ghost: 'hover:bg-accent hover:text-foreground',
				link: 'text-muted-foreground hover:text-primary'
			}
		},
		defaultVariants: {
			variant: 'default'
		}
	});

	export type BadgeVariant = VariantProps<typeof badgeVariants>['variant'];
</script>

<script lang="ts">
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLAnchorAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		href,
		class: className,
		variant = 'default',
		children,
		...restProps
	}: WithElementRef<HTMLAnchorAttributes> & {
		variant?: BadgeVariant;
	} = $props();
</script>

<svelte:element
	this={href ? 'a' : 'span'}
	bind:this={ref}
	data-slot="badge"
	{href}
	class={cn(badgeVariants({ variant }), className)}
	{...restProps}
>
	{@render children?.()}
</svelte:element>
