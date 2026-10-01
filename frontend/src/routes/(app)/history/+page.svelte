<script lang="ts">
	import History from '@lucide/svelte/icons/history';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>История · Kōri</title></svelte:head>

<!-- Stub until F-04 (tech.md §22). -->
<div class="space-y-6">
	<PageHeader title="История" description="Прошлые диалоги и поиск по ним" />
	<EmptyState
		icon={History}
		title="Диалогов пока нет"
		description="Здесь появятся диалоги с аналитиком: поиск, переименование и архив."
	/>
</div>
