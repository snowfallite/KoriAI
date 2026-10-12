<script lang="ts" module>
	import SvelteMarkdown, {
		type CodeSnippetProps,
		type LinkSnippetProps,
		type MarkedExtension
	} from '@humanspeak/svelte-markdown';
	import type { Snippet } from 'svelte';

	const CITATION = /^\[(s[0-9]+)\]/;
	// A number as the answer prints it (tech.md §9.10): a date, a time, or a sign, digit groups, a
	// decimal part, a scale and a unit. A letter or a digit right after it means a word instead.
	const SPACE = '[ \\u00a0\\u202f]';
	const NUMBER = new RegExp(
		'^(?:\\d{2}\\.\\d{2}\\.\\d{4}|\\d{1,2}:\\d{2}|[+\\-\\u2212]?(?:\\d{1,3}(?:' +
			SPACE +
			'\\d{3})+|\\d+)(?:[.,]\\d+)?(?:' +
			SPACE +
			'?(?:млн|млрд|трлн|тыс\\.))?(?:' +
			SPACE +
			'?(?:%|₽|\\$|€))?)(?![\\p{L}\\p{N}_])',
		'u'
	);
	// Where a number may start: not inside a word, a name like GigaChat-2 or a range like 2020-2025.
	const NUMBER_START = /(?<![\p{L}\p{N}_.,:\-−])[+\-−]?\d/u;
	const WORDY = /[\p{L}\p{N}_.,:\-−]$/u;

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
			extensions: [
				{
					// [s1] cites a source of the answer (tech.md §9.9).
					name: 'citation',
					level: 'inline',
					start: (src: string) => src.search(/\[s[0-9]/),
					tokenizer(src: string) {
						const match = CITATION.exec(src);
						if (match) return { type: 'citation', raw: match[0], id: match[1] };
					}
				},
				{
					// ==phrase== is the key phrase of the answer: the printed highlight of v3.
					name: 'highlight',
					level: 'inline',
					start: (src: string) => {
						const at = src.indexOf('==');
						return at < 0 ? undefined : at;
					},
					tokenizer(src: string) {
						const match = /^==(?=\S)([^\n]*?\S)==(?!=)/.exec(src);
						if (match?.[1])
							return {
								type: 'highlight',
								raw: match[0],
								text: match[1],
								tokens: this.lexer.inlineTokens(match[1])
							};
					}
				},
				{
					// Facts of the answer stand out from its prose: numbers in the ink color, a loss red.
					name: 'number',
					level: 'inline',
					start: (src: string) => {
						const at = src.search(NUMBER_START);
						return at < 0 ? undefined : at;
					},
					tokenizer(src: string, tokens) {
						if (WORDY.test(tokens.at(-1)?.raw ?? '')) return;
						const match = NUMBER.exec(src);
						if (match)
							return {
								type: 'number',
								raw: match[0],
								text: match[0],
								loss: /^[-−]/.test(match[0])
							};
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

<!-- eslint-disable svelte/no-navigation-without-resolve -- only external http(s) links here -->
<!-- The answer of v3 (docs/ui-references/kori-v3): grey prose at 16/26, facts in the ink color
     without bold, block headings bold, sources as red superscript numbers. -->
<div
	class="space-y-3 text-body break-words text-prose [&_:not(pre)>code]:bg-muted [&_:not(pre)>code]:px-1 [&_blockquote]:border-l [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_h1]:mt-8 [&_h1]:text-[16px]/6 [&_h1]:font-bold [&_h1]:text-foreground [&_h2]:mt-8 [&_h2]:text-[16px]/6 [&_h2]:font-bold [&_h2]:text-foreground [&_h3]:mt-8 [&_h3]:text-[16px]/6 [&_h3]:font-bold [&_h3]:text-foreground [&_li]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_strong]:font-normal [&_strong]:text-foreground [&_table]:w-full [&_table]:text-ui [&_td]:border-b [&_td]:border-line-faint [&_td]:p-1.5 [&_th]:border-b [&_th]:p-1.5 [&_th]:text-left [&_th]:text-caption [&_th]:font-normal [&_th]:text-grey-600 [&_th]:uppercase [&_ul]:list-['→_'] [&_ul]:pl-5"
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
					class="text-foreground underline underline-offset-2 hover:text-primary"
					>{@render children?.()}</a
				>
			{:else}
				{@render children?.()}
			{/if}
		{/snippet}

		<!-- Pictures come only as artifacts through the media proxy (tech.md AD-09). -->
		{#snippet image()}{/snippet}

		{#snippet code({ text }: CodeSnippetProps)}
			<div class="relative">
				<pre class="overflow-x-auto bg-muted p-3 pr-10 text-ui"><code>{text}</code></pre>
				<div class="absolute top-1 right-1"><CopyButton {text} /></div>
			</div>
		{/snippet}

		{#snippet number({ text, loss }: { text: string; loss: boolean })}
			<span data-number={loss ? 'loss' : 'value'} class={loss ? 'text-negative' : 'text-foreground'}
				>{text}</span
			>
		{/snippet}

		{#snippet highlight({ children }: { children?: Snippet })}
			<mark class="bg-transparent ki-highlight px-1 text-foreground">{@render children?.()}</mark>
		{/snippet}

		<!-- A known citation becomes a red superscript number; an unknown one disappears. -->
		{#snippet citation({ id }: { id: string })}
			{@const cited = byId.get(id)}
			{@const url = safeUrl(cited?.url)}
			{#if cited && url}
				<sup class="ml-0.5 text-[10px]"
					><a
						href={url}
						title={cited.title}
						target="_blank"
						rel="noopener noreferrer nofollow"
						class="text-primary hover:underline">{id.slice(1)}</a
					></sup
				>
			{:else if cited}
				<sup class="ml-0.5 text-[10px] text-primary" title={cited.title}>{id.slice(1)}</sup>
			{/if}
		{/snippet}
	</SvelteMarkdown>
</div>
