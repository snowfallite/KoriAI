<script lang="ts">
	import { Button, type ButtonVariant } from './index';

	// A button the way §13.1 builds an action: the glyph cell first when the glyph means
	// something, the label alone when it does not (glyph null).
	let {
		variant,
		glyph = '→',
		label = 'Войти'
	}: { variant: ButtonVariant; glyph?: string | null; label?: string } = $props();
</script>

<Button {variant}
	>{#if glyph}<span data-slot="button-glyph" aria-hidden="true">{glyph}</span>{/if}{label}</Button
>
