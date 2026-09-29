<script lang="ts">
	import type { SourceRef } from '$lib/types';
	import { formatDate } from '$lib/utils/format';

	let { sources }: { sources: SourceRef[] } = $props();

	const KIND: Record<SourceRef['kind'], string> = {
		web: 'веб',
		document: 'документ',
		tinvest: 'Т-Инвестиции',
		edisclosure: 'e-disclosure'
	};

	// Only http(s) leaves the page (tech.md §3.5).
	const safe = (url: string | null) => (url && /^https?:\/\//i.test(url) ? url : null);

	function details(source: SourceRef): string {
		const date = source.published_at ? formatDate(source.published_at) : null;
		const page = source.page ? `стр. ${source.page}` : null;
		return [KIND[source.kind], source.publisher, date, page].filter(Boolean).join(' · ');
	}
</script>

{#if sources.length}
	<ol class="space-y-1.5 text-xs" aria-label="Источники">
		{#each sources as source (source.local_id)}
			{@const url = safe(source.url)}
			<li class="flex gap-2">
				<span class="text-muted-foreground">{source.local_id.slice(1)}.</span>
				<div class="min-w-0">
					{#if url}
						<a
							href={url}
							target="_blank"
							rel="noopener noreferrer nofollow"
							class="underline-offset-2 hover:underline">{source.title}</a
						>
					{:else}
						<span>{source.title}</span>
					{/if}
					<span class="text-muted-foreground">· {details(source)}</span>
					{#if source.snippet}
						<p class="mt-0.5 line-clamp-2 text-muted-foreground">{source.snippet}</p>
					{/if}
				</div>
			</li>
		{/each}
	</ol>
{/if}
