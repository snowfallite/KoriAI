<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import { signOut } from '$lib/state/session.svelte';
	import { Button } from '$lib/ui/button';

	let { data } = $props();
</script>

<svelte:head><title>Настройки · Kōri</title></svelte:head>

<!-- Stub until F-01 and F-02 (tech.md §22). -->
<PageHeader title="Настройки" />
<div class="space-y-8 p-4 md:p-12">
	<EmptyState
		title="Настроек пока нет"
		description="Здесь появятся подключение Т-Инвестиций, выбор модели, расход и профиль."
	/>
	<!-- A phone has no sidebar: the theme and the exit live here until F-02 builds Профиль. -->
	<section
		aria-label="Сессия"
		class="flex flex-wrap items-center justify-between gap-4 border p-5 md:hidden"
	>
		<p class="min-w-0 truncate text-ui">{data.me.user.email}</p>
		<div class="flex items-center gap-4">
			<ThemeToggle />
			<Button variant="link" onclick={signOut}>Выйти</Button>
		</div>
	</section>
</div>
