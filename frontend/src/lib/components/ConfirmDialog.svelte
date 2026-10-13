<script lang="ts">
	import * as AlertDialog from '$lib/ui/alert-dialog';

	let {
		open = $bindable(false),
		title,
		description,
		confirmLabel = 'Подтвердить',
		destructive = false,
		onConfirm
	}: {
		open: boolean;
		title: string;
		description?: string;
		confirmLabel?: string;
		destructive?: boolean;
		onConfirm: () => Promise<void> | void;
	} = $props();

	let pending = $state(false);

	// The dialog stays open until the action finishes; a failure leaves it open to retry.
	async function confirm() {
		pending = true;
		try {
			await onConfirm();
			open = false;
		} finally {
			pending = false;
		}
	}
</script>

<!-- A white panel up to 420 px (kori-v3, Карточки): a black title strip with ×, the text, a strip
     of two 44 px buttons. A white hairline keeps the strip apart from the dimmed page. -->
<AlertDialog.Root bind:open>
	<AlertDialog.Content
		class="max-w-[420px] gap-0 border border-background p-0 data-[size=default]:max-w-[420px] data-[size=default]:sm:max-w-[420px]"
	>
		<div
			class="flex items-center justify-between gap-4 bg-foreground py-3.5 pr-2 pl-4 text-background"
		>
			<AlertDialog.Title class="text-[22px]/7 font-normal">{title}</AlertDialog.Title>
			<AlertDialog.Cancel
				variant="ghost"
				size="icon-sm"
				aria-label="Закрыть"
				class="text-lg text-background hover:bg-transparent hover:text-primary focus-visible:outline-background"
				disabled={pending}>×</AlertDialog.Cancel
			>
		</div>
		{#if description}
			<AlertDialog.Description class="px-4 pt-5 pb-6 text-[14px]/[22px] text-foreground">
				{description}
			</AlertDialog.Description>
		{/if}
		<div class="flex">
			<AlertDialog.Cancel variant="secondary" class="h-11 flex-1 justify-start" disabled={pending}>
				<span data-slot="button-glyph" aria-hidden="true">×</span>Отмена
			</AlertDialog.Cancel>
			<AlertDialog.Action
				variant={destructive ? 'destructive' : 'default'}
				class="h-11 flex-1 justify-start"
				disabled={pending}
				onclick={confirm}
			>
				<span data-slot="button-glyph" aria-hidden="true">→</span>{confirmLabel}
			</AlertDialog.Action>
		</div>
	</AlertDialog.Content>
</AlertDialog.Root>
