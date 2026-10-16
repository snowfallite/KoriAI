<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>История · Kōri</title></svelte:head>

<!-- Stub until F-04 (tech.md §22). -->
<PageHeader title="История" description="Прошлые диалоги и поиск по ним" />
<div class="p-4 md:p-12">
	<EmptyState
		title="Диалогов пока нет"
		description="Здесь появятся диалоги с аналитиком: поиск, переименование и архив."
	/>
</div>
