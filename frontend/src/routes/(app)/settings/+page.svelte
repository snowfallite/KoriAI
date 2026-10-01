<script lang="ts">
	import Settings from '@lucide/svelte/icons/settings';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
</script>

<svelte:head><title>Настройки · Kōri</title></svelte:head>

<!-- Stub until F-01 and F-02 (tech.md §22). -->
<div class="space-y-6">
	<PageHeader title="Настройки" description="Брокер, модель, расход и профиль" />
	<EmptyState
		icon={Settings}
		title="Настройки готовятся"
		description="Здесь появятся токен брокера, выбор модели, расход и профиль."
	/>
</div>
