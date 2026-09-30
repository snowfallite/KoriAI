<script lang="ts">
	import CircleAlert from '@lucide/svelte/icons/circle-alert';
	import RotateCw from '@lucide/svelte/icons/rotate-cw';
	import type { ApiError } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { Button } from '$lib/ui/button';

	let { error, onRetry }: { error: ApiError; onRetry?: () => void } = $props();
</script>

<Alert.Root variant="destructive">
	<CircleAlert />
	<Alert.Title>{error.message}</Alert.Title>
	{#if error.request_id}
		<!-- The request id lets support find the failure in the logs (tech.md §3.6). -->
		<Alert.Description>Код запроса: {error.request_id}</Alert.Description>
	{/if}
	{#if onRetry}
		<Alert.Action>
			<Button variant="outline" size="sm" onclick={onRetry}>
				<RotateCw />
				Повторить
			</Button>
		</Alert.Action>
	{/if}
</Alert.Root>
