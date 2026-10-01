<script lang="ts">
	import MessageSquare from '@lucide/svelte/icons/message-square';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>Чат · Kōri</title></svelte:head>

<!-- Stub until F-03 (tech.md §22). -->
<div class="space-y-6">
	<PageHeader title="Чат" description="Вопросы о портфеле, инструментах и эмитентах" />
	<EmptyState
		icon={MessageSquare}
		title="Чат готовится"
		description="Здесь аналитик ответит на вопросы о портфеле и покажет графики, таблицы и источники."
	/>
</div>
