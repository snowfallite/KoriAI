<script lang="ts">
	import AppShell from '$lib/components/AppShell.svelte';
	import { NAV } from '$lib/nav';

	let { data, children } = $props();
</script>

<AppShell nav={NAV} user={data.me.user}>{@render children()}</AppShell>
