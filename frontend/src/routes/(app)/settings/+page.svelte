<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import { signOut } from '$lib/state/session.svelte';
	import { Button } from '$lib/ui/button';
	import BrokerSection from './components/BrokerSection.svelte';

	let { data } = $props();
</script>

<svelte:head><title>Настройки · Kōri</title></svelte:head>

<!-- The sections of tech.md §13.3: Брокер now; F-02 adds Модель and Профиль, F-06 Расход. -->
<PageHeader title="Настройки" />
<div class="max-w-[1200px] space-y-8 p-4 md:p-12">
	<BrokerSection broker={data.me.broker} />
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
