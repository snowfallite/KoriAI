<script lang="ts" module>
	import { type VariantProps, tv } from 'tailwind-variants';
	import { cn, type WithElementRef } from '$lib/utils/cn.js';
	import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';

	// The ink label of the main action: a step greyer on hover, whichever theme it stands in.
	const STEP = 'hover:bg-[color-mix(in_srgb,var(--foreground)_85%,var(--background))]';

	export const buttonVariants = tv({
		base: "group/button inline-flex shrink-0 items-center justify-center gap-2 rounded-none border border-transparent bg-clip-padding text-ui font-normal whitespace-nowrap transition-colors outline-none select-none active:not-aria-[haspopup]:translate-y-px aria-invalid:border-destructive disabled:pointer-events-none disabled:border-transparent disabled:bg-grey-200 disabled:bg-none disabled:text-grey-600 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 has-[>[data-slot=button-glyph]]:gap-4 has-[>[data-slot=button-glyph]]:pl-0 [&>[data-slot=button-glyph]]:grid [&>[data-slot=button-glyph]]:aspect-square [&>[data-slot=button-glyph]]:self-stretch [&>[data-slot=button-glyph]]:place-items-center [&>[data-slot=button-glyph]]:text-base [&>[data-slot=button-glyph]]:tracking-normal [&>[data-slot=button-glyph]]:normal-case disabled:[&>[data-slot=button-glyph]]:bg-grey-300 disabled:[&>[data-slot=button-glyph]]:bg-none disabled:[&>[data-slot=button-glyph]]:text-grey-600",
		variants: {
			variant: {
				// Kōri v4 (tech.md §13.1): a label in normal case; a glyph cell comes only from a
				// button-glyph child, where the glyph means something. The main one has a red cell and
				// a label in the ink color, destructive a red-deep cell, the stepped grey one a grey
				// ladder, the AI one an ignite cell on the fade. No button rests on a red field.
				default: `bg-foreground text-background ${STEP} [&>[data-slot=button-glyph]]:bg-primary [&>[data-slot=button-glyph]]:text-primary-foreground`,
				destructive: `bg-foreground text-background ${STEP} [&>[data-slot=button-glyph]]:bg-primary-deep [&>[data-slot=button-glyph]]:text-primary-deep-foreground`,
				secondary:
					'bg-grey-300 text-black hover:bg-grey-200 aria-expanded:bg-grey-200 [&>[data-slot=button-glyph]]:bg-grey-400',
				outline:
					'border-foreground bg-transparent hover:bg-foreground hover:text-background aria-expanded:bg-foreground aria-expanded:text-background',
				ghost:
					'hover:bg-accent hover:text-foreground aria-expanded:bg-accent aria-expanded:text-foreground disabled:bg-transparent',
				link: 'text-caps text-muted-foreground hover:text-primary disabled:bg-transparent',
				ai: 'ki-fade text-black hover:bg-primary hover:bg-none [&>[data-slot=button-glyph]]:ki-ignite [&>[data-slot=button-glyph]]:text-white'
			},
			size: {
				default: 'h-10 px-4 has-[>[data-slot=button-glyph]]:pr-5',
				xs: "h-6 gap-1 px-2 text-caption has-[>[data-slot=button-glyph]]:pr-2 [&_svg:not([class*='size-'])]:size-3",
				sm: "h-8 gap-1.5 px-3 has-[>[data-slot=button-glyph]]:pr-4 [&_svg:not([class*='size-'])]:size-3.5",
				lg: 'h-12 px-5 has-[>[data-slot=button-glyph]]:pr-6',
				icon: 'size-10',
				'icon-xs': "size-6 [&_svg:not([class*='size-'])]:size-3",
				'icon-sm': 'size-7',
				'icon-lg': 'size-12'
			}
		},
		compoundVariants: [
			// A link is text: no box around it.
			{ variant: 'link', class: 'h-auto px-0' },
			// The send button of the question field: a square of ignite with a white arrow.
			{
				variant: 'ai',
				size: ['icon', 'icon-xs', 'icon-sm', 'icon-lg'],
				class: 'ki-ignite text-base text-white'
			}
		],
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
