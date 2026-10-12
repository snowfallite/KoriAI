<script lang="ts">
	import { mode, setMode } from 'mode-watcher';
	import * as ToggleGroup from '$lib/ui/toggle-group';

	type Theme = 'dark' | 'light';

	const THEMES: { value: Theme; label: string }[] = [
		{ value: 'dark', label: 'Ночь' },
		{ value: 'light', label: 'День' }
	];

	// Night is the Kïoku default until the reader chooses (routes/+layout.svelte).
	const current = $derived<Theme>(mode.current === 'light' ? 'light' : 'dark');
</script>

<!-- Two segments in the ink color, the chosen one white (tech.md §13.3); a click on it keeps it. -->
<ToggleGroup.Root
	type="single"
	variant="outline"
	size="sm"
	aria-label="Тема"
	bind:value={() => current, (next) => next && setMode(next as Theme)}
>
	{#each THEMES as theme (theme.value)}
		<ToggleGroup.Item value={theme.value} class="text-[10px]">{theme.label}</ToggleGroup.Item>
	{/each}
</ToggleGroup.Root>
