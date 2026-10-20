<script lang="ts">
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import CopyButton from './CopyButton.svelte';

	let { error, onRetry }: { error: ApiError; onRetry?: () => void } = $props();
</script>

<!-- A failed load (tech.md §13.2, kori-v4 «Ошибка загрузки»): a frame with a red-deep bar on the
     left, the message, the request code to copy and an outline Повторить. No × cell: it reads as
     «close» and closes nothing. -->
<div
	role="alert"
	class="flex flex-col items-start gap-2.5 border border-l-2 border-l-primary-deep px-8 py-7"
>
	<p class="text-lead">{error.message}</p>
	{#if error.request_id}
		<!-- The request id lets support find the failure in the logs (tech.md §3.6). -->
		<p class="flex flex-wrap items-center gap-x-2 text-caps text-grey-600">
			<span>Код запроса {error.request_id}</span>
			<CopyButton text={error.request_id} label="Копировать код запроса" />
		</p>
	{/if}
	{#if onRetry}
		<Button variant="outline" class="mt-1.5" onclick={onRetry}>Повторить</Button>
	{/if}
</div>
