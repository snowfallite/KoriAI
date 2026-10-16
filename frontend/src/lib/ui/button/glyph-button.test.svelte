<script lang="ts">
	import { Button, type ButtonVariant } from './index';

	// A button with a glyph cell, the way §13.1 builds an action: the cell, then the label.
	let {
		variant,
		glyph = '→',
		label = 'Войти'
	}: { variant: ButtonVariant; glyph?: string; label?: string } = $props();
</script>

<Button {variant}><span data-slot="button-glyph" aria-hidden="true">{glyph}</span>{label}</Button>
