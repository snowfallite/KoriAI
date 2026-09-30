<script lang="ts" module>
	import { type VariantProps, tv } from 'tailwind-variants';
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';

	export const buttonVariants = tv({
		base: "focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:aria-invalid:border-destructive/50 rounded-none border border-transparent bg-clip-padding text-xs font-medium focus-visible:ring-1 aria-invalid:ring-1 active:not-aria-[haspopup]:translate-y-px [&_svg:not([class*='size-'])]:size-4 group/button inline-flex shrink-0 items-center justify-center whitespace-nowrap transition-all outline-none select-none disabled:pointer-events-none disabled:border-transparent disabled:bg-grey-200 disabled:bg-none disabled:text-grey-600 has-[>[data-slot=button-glyph]]:gap-3 has-[>[data-slot=button-glyph]]:pl-0 [&>[data-slot=button-glyph]]:grid [&>[data-slot=button-glyph]]:aspect-square [&>[data-slot=button-glyph]]:self-stretch [&>[data-slot=button-glyph]]:place-items-center [&>[data-slot=button-glyph]]:text-base [&>[data-slot=button-glyph]]:tracking-normal disabled:[&>[data-slot=button-glyph]]:bg-grey-300 disabled:[&>[data-slot=button-glyph]]:bg-none disabled:[&>[data-slot=button-glyph]]:text-grey-600 [&_svg]:pointer-events-none [&_svg]:shrink-0",
		variants: {
			variant: {
				// Kïoku (tech.md §13.1): the CTA and the outline speak in caps and invert on hover, the
				// stepped grey action lightens a step, destructive is the red-deep plate, the AI action
				// fades red into white. A glyph cell is grey-400 on grey, ki-ignite on red.
				default:
					'bg-primary text-primary-foreground uppercase tracking-wider hover:bg-foreground hover:text-background [&>[data-slot=button-glyph]]:ki-ignite [&>[data-slot=button-glyph]]:text-white',
				outline:
					'border-foreground bg-transparent uppercase tracking-wider hover:bg-foreground hover:text-background aria-expanded:bg-foreground aria-expanded:text-background',
				secondary:
					'bg-secondary text-secondary-foreground hover:bg-grey-200 aria-expanded:bg-grey-200 [&>[data-slot=button-glyph]]:bg-grey-400',
				ghost:
					'hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground disabled:bg-transparent',
				destructive:
					'bg-primary-deep text-primary-deep-foreground hover:bg-primary hover:text-primary-foreground',
				link: 'text-muted-foreground uppercase tracking-wider hover:text-primary disabled:bg-transparent',
				ai: 'ki-fade text-black hover:bg-primary hover:bg-none [&>[data-slot=button-glyph]]:ki-ignite [&>[data-slot=button-glyph]]:text-white'
			},
			size: {
				default:
					'h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2',
				xs: "h-6 gap-1 rounded-none px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
				sm: "h-7 gap-1 rounded-none px-2.5 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
				lg: 'h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2',
				icon: 'size-8',
				'icon-xs': "size-6 rounded-none [&_svg:not([class*='size-'])]:size-3",
				'icon-sm': 'size-7 rounded-none',
				'icon-lg': 'size-9'
			}
		},
		defaultVariants: {
			variant: 'default',
			size: 'default'
		}
	});

	export type ButtonVariant = VariantProps<typeof buttonVariants>['variant'];
	export type ButtonSize = VariantProps<typeof buttonVariants>['size'];

	export type ButtonProps = WithElementRef<HTMLButtonAttributes> &
		WithElementRef<HTMLAnchorAttributes> & {
			variant?: ButtonVariant;
			size?: ButtonSize;
		};
</script>

<script lang="ts">
	let {
		class: className,
		variant = 'default',
		size = 'default',
		ref = $bindable(null),
		href = undefined,
		type = 'button',
		disabled,
		children,
		...restProps
	}: ButtonProps = $props();
</script>

{#if href}
	<a
		bind:this={ref}
		data-slot="button"
		class={cn(buttonVariants({ variant, size }), className)}
		href={disabled ? undefined : href}
		aria-disabled={disabled}
		role={disabled ? 'link' : undefined}
		tabindex={disabled ? -1 : undefined}
		{...restProps}
	>
		{@render children?.()}
	</a>
{:else}
	<button
		bind:this={ref}
		data-slot="button"
		class={cn(buttonVariants({ variant, size }), className)}
		{type}
		{disabled}
		{...restProps}
	>
		{@render children?.()}
	</button>
{/if}
