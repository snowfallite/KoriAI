<script lang="ts">
	import type { ApiError } from '$lib/types';
	import { Button } from '$lib/ui/button';

	let { error, onRetry }: { error: ApiError; onRetry?: () => void } = $props();
</script>

<!-- A failed load (kori-v3, Карточки): the × cell in red-deep, the message, the request code and
     an outline Повторить. -->
<div role="alert" class="flex items-start gap-4 border p-8">
	<span
		aria-hidden="true"
		class="grid size-9 shrink-0 place-items-center bg-primary-deep text-[17px] text-primary-deep-foreground"
		>×</span
	>
	<div class="flex min-w-0 flex-col items-start gap-2.5">
		<p class="text-lead">{error.message}</p>
		{#if error.request_id}
			<!-- The request id lets support find the failure in the logs (tech.md §3.6). -->
			<p class="text-caption text-grey-600">
				<span class="uppercase">Код запроса:</span>
				{error.request_id}
			</p>
		{/if}
		{#if onRetry}
			<Button variant="outline" class="mt-2" onclick={onRetry}>Повторить</Button>
		{/if}
	</div>
</div>
