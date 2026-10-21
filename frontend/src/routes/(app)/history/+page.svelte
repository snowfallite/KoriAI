<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>История · Kōri</title></svelte:head>

<!-- Stub until F-04 (tech.md §22). -->
<PageHeader title="История" />
<div class="p-4 md:p-12">
	<EmptyState title="Чатов пока нет" description="Здесь будут ваши прошлые чаты и поиск по ним." />
</div>
