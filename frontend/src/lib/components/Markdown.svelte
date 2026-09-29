<script lang="ts" module>
	import SvelteMarkdown, {
		type CodeSnippetProps,
		type LinkSnippetProps,
		type MarkedExtension
	} from '@humanspeak/svelte-markdown';

	const CITATION = /^\[(s[0-9]+)\]/;

	const extensions: MarkedExtension[] = [
		{
			// Raw HTML of the answer stays text (tech.md §3.5): marked still finds the tags, so
			// nothing inside them turns into markdown, but they come back as plain text tokens.
			tokenizer: {
				html(src) {
					const raw = this.rules.block.html.exec(src)?.[0];
					const text = raw?.trimEnd();
					if (raw)
						return { type: 'paragraph', raw, text, tokens: [{ type: 'text', raw, text }] } as never;
				},
				tag(src) {
					const raw = this.rules.inline.tag.exec(src)?.[0];
					if (raw) return { type: 'text', raw, text: raw } as never;
				}
			},
			// [s1] cites a source of the answer (tech.md §9.9).
			extensions: [
				{
					name: 'citation',
					level: 'inline',
					start: (src: string) => src.search(/\[s[0-9]/),
					tokenizer(src: string) {
						const match = CITATION.exec(src);
						if (match) return { type: 'citation', raw: match[0], id: match[1] };
					}
				}
			]
		}
	];

	// Only http(s) leaves the page; everything else stays text (tech.md §3.5).
	const safeUrl = (url: string | null | undefined) =>
		url && /^https?:\/\//i.test(url.trim()) ? url.trim() : '';
</script>

<script lang="ts">
	import type { SourceRef } from '$lib/types';
	import CopyButton from './CopyButton.svelte';

	let {
		source,
		sources = [],
		streaming = false
	}: { source: string; sources?: SourceRef[]; streaming?: boolean } = $props();

	const byId = $derived(new Map(sources.map((s) => [s.local_id, s])));
</script>

<div
	class="space-y-3 text-sm/6 break-words [&_:not(pre)>code]:bg-muted [&_:not(pre)>code]:px-1 [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold [&_li]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_table]:w-full [&_table]:text-xs [&_td]:border-b [&_td]:p-1.5 [&_th]:border-b [&_th]:p-1.5 [&_th]:text-left [&_ul]:list-disc [&_ul]:pl-5"
>
	<SvelteMarkdown
		{source}
		{streaming}
		{extensions}
		sanitizeUrl={safeUrl}
		options={{ headerIds: false }}
	>
		{#snippet link({ href, title, children }: LinkSnippetProps)}
			{#if href}
				<a
					{href}
					{title}
					target="_blank"
					rel="noopener noreferrer nofollow"
					class="underline underline-offset-2 hover:text-primary">{@render children?.()}</a
				>
			{:else}
				{@render children?.()}
			{/if}
		{/snippet}

		<!-- Pictures come only as artifacts through the media proxy (tech.md AD-09). -->
		{#snippet image()}{/snippet}

		{#snippet code({ text }: CodeSnippetProps)}
			<div class="relative">
				<pre class="overflow-x-auto bg-muted p-3 pr-10 text-xs"><code>{text}</code></pre>
				<div class="absolute top-1 right-1"><CopyButton {text} /></div>
			</div>
		{/snippet}

		<!-- A known citation becomes a footnote; an unknown one disappears. -->
		{#snippet citation({ id }: { id: string })}
			{@const cited = byId.get(id)}
			{@const url = safeUrl(cited?.url)}
			{#if cited && url}
				<sup
					><a
						href={url}
						title={cited.title}
						target="_blank"
						rel="noopener noreferrer nofollow"
						class="text-muted-foreground hover:text-primary">{id.slice(1)}</a
					></sup
				>
			{:else if cited}
				<sup class="text-muted-foreground" title={cited.title}>{id.slice(1)}</sup>
			{/if}
		{/snippet}
	</SvelteMarkdown>
</div>
