<script lang="ts">
	import ImageOff from '@lucide/svelte/icons/image-off';
	import type { ArtifactOut, ImageSpec } from '$lib/types';
	import { Skeleton } from '$lib/ui/skeleton';
	import { cn } from '$lib/utils/cn';

	let { artifact }: { artifact: ArtifactOut } = $props();

	const spec = $derived(artifact.spec as ImageSpec);
	let status = $state<'loading' | 'loaded' | 'error'>('loading');

	const WIDTH: Record<ImageSpec['size'], string> = {
		sm: 'max-w-40',
		md: 'max-w-sm',
		lg: 'max-w-2xl'
	};
</script>

<!-- The picture comes only through the media proxy of the API (tech.md AD-09). -->
<figure class={cn('space-y-1', WIDTH[spec.size])}>
	{#if artifact.image_url && status !== 'error'}
		<div class="relative">
			{#if status === 'loading'}
				<Skeleton class="aspect-video w-full" />
				<span class="sr-only">Загрузка изображения</span>
			{/if}
			<img
				src={artifact.image_url}
				alt={spec.alt}
				class={cn('w-full', status !== 'loaded' && 'hidden')}
				onload={() => (status = 'loaded')}
				onerror={() => (status = 'error')}
			/>
		</div>
	{:else}
		<div
			class="flex aspect-video w-full flex-col items-center justify-center gap-2 bg-muted text-muted-foreground"
			role="img"
			aria-label={spec.alt}
		>
			<ImageOff class="size-5" aria-hidden="true" />
			<span class="text-xs">Изображение недоступно</span>
		</div>
	{/if}
	{#if spec.caption}
		<figcaption class="text-xs text-muted-foreground">{spec.caption}</figcaption>
	{/if}
</figure>
