<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>Чат · Kōri</title></svelte:head>

<!-- Stub until F-03 (tech.md §22): what the tab will hold, in the words of the reader. -->
<PageHeader title="Чат" />
<div class="p-4 md:p-12">
	<EmptyState
		title="Чата пока нет"
		description="Здесь можно будет спросить о портфеле: ответ придёт с таблицами, графиками и ссылками на источники."
	/>
</div>
