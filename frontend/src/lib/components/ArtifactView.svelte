<script lang="ts">
	import type { ArtifactOut, ChartSpec, TableSpec } from '$lib/types';
	import ArtifactImage from './ArtifactImage.svelte';
	import ArtifactTable from './ArtifactTable.svelte';
	import ChartView from './ChartView.svelte';

	let { artifact }: { artifact: ArtifactOut } = $props();
</script>

<!-- kind tells which spec the artifact carries (tech.md §9.9). -->
{#if artifact.kind === 'chart'}
	<ChartView spec={artifact.spec as ChartSpec} />
{:else if artifact.kind === 'table'}
	<ArtifactTable spec={artifact.spec as TableSpec} />
{:else}
	<ArtifactImage {artifact} />
{/if}
