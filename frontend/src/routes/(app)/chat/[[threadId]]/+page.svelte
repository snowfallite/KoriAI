<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>Чат · Kōri</title></svelte:head>

<!-- Stub until F-03 (tech.md §22). -->
<PageHeader title="Чат" description="Вопросы о портфеле, инструментах и эмитентах" />
<div class="p-4 md:p-12">
	<EmptyState
		title="Чат готовится"
		description="Здесь аналитик ответит на вопросы о портфеле и покажет графики, таблицы и источники."
	/>
</div>
