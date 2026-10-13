<script lang="ts">
	import type { Snippet } from 'svelte';
	import { Label } from '$lib/ui/label';

	let {
		id,
		label,
		error = null,
		link,
		aside,
		hint,
		children
	}: {
		/** The id of the control; its error line takes `${id}-error`. */
		id: string;
		label: string;
		/** The line of an error the API tied to this field. */
		error?: string | null;
		/** A way out of the error, such as Войти for a taken email. */
		link?: { href: string; label: string };
		/** A caption or a control at the right of the label. */
		aside?: Snippet;
		hint?: Snippet;
		children: Snippet;
	} = $props();
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- the page resolves the link -->
<div class="flex flex-col gap-1.5 md:gap-2">
	<div class="flex items-baseline justify-between gap-4">
		<Label for={id}>{label}</Label>
		{@render aside?.()}
	</div>
	{@render children()}
	<!-- An error at its field (kori-v3, Регистрация): a red ×, the reason in black, a way out. -->
	{#if error}
		<p id="{id}-error" role="alert" class="flex items-baseline gap-2 text-ui">
			<span aria-hidden="true" class="text-primary-deep">×</span>
			<span
				>{error}{#if link}. <a href={link.href} class="underline underline-offset-3"
						>{link.label}<span aria-hidden="true"> →</span></a
					>{/if}</span
			>
		</p>
	{/if}
	{@render hint?.()}
</div>
