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

	/** «Т-Инвестиции · портфель acc1, acc2 · 10.10.2026»: who, what, when, where. */
	function line(source: SourceRef): string {
		const date = source.published_at ? formatDate(source.published_at) : null;
		const page = source.page ? `стр. ${source.page}` : null;
		return [source.publisher ?? KIND[source.kind], source.title, date, page]
			.filter(Boolean)
			.join(' · ');
	}
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- only external http(s) links here -->
{#if sources.length}
	<!-- Sources under the answer (kori-v3, chat-thread): a red number, the line, an arrow. -->
	<div class="border-t pt-3.5">
		<p class="mb-2.5 text-caption text-grey-600 uppercase">Источники</p>
		<ol class="space-y-1.5 text-ui text-muted-foreground" aria-label="Источники">
			{#each sources as source (source.local_id)}
				{@const url = safe(source.url)}
				<li>
					{#if url}
						<a
							href={url}
							target="_blank"
							rel="noopener noreferrer nofollow"
							class="flex gap-3 hover:text-primary"
						>
							<span class="text-primary">{source.local_id.slice(1)}</span>
							<span class="min-w-0">{line(source)}</span>
							<span aria-hidden="true">→</span>
						</a>
					{:else}
						<p class="flex gap-3">
							<span class="text-primary">{source.local_id.slice(1)}</span>
							<span class="min-w-0">{line(source)}</span>
						</p>
					{/if}
					{#if source.snippet}
						<p class="mt-0.5 line-clamp-2 pl-6 text-grey-600">{source.snippet}</p>
					{/if}
				</li>
			{/each}
		</ol>
	</div>
{/if}
