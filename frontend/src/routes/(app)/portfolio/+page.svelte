<script lang="ts">
	import BriefcaseBusiness from '@lucide/svelte/icons/briefcase-business';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>Портфель · Kōri</title></svelte:head>

<!-- Stub until S1-11 (tech.md §22). -->
<div class="space-y-6">
	<PageHeader title="Портфель" description="Счета, структура и позиции" />
	<EmptyState
		icon={BriefcaseBusiness}
		title="Портфель готовится"
		description="Здесь появятся счета, структура и позиции из Т-Инвестиций."
	/>
</div>
