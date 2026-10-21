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

<!-- A white panel up to 420 px (tech.md §13.2, kori-v4 «Диалог удаления»): a black title strip,
     the text, a strip of two 44 px buttons. One × a dialog, at the delete action; Отмена and Esc
     close it. A white hairline keeps the panel apart from the dimmed page. -->
<AlertDialog.Root bind:open>
	<AlertDialog.Content
		class="max-w-[420px] gap-0 border border-background p-0 data-[size=default]:max-w-[420px] data-[size=default]:sm:max-w-[420px]"
	>
		<AlertDialog.Title class="bg-foreground px-4 py-3.5 text-[22px]/7 font-normal text-background">
			{title}
		</AlertDialog.Title>
		{#if description}
			<AlertDialog.Description class="px-4 pt-5 pb-6 text-[14px]/[22px] text-foreground">
				{description}
			</AlertDialog.Description>
		{/if}
		<div class="flex">
			<AlertDialog.Cancel
				variant="secondary"
				class="h-11 flex-1 justify-start px-4"
				disabled={pending}>Отмена</AlertDialog.Cancel
			>
			<AlertDialog.Action
				variant={destructive ? 'destructive' : 'default'}
				class="h-11 flex-1 justify-start has-[>[data-slot=button-glyph]]:gap-3.5"
				disabled={pending}
				onclick={confirm}
			>
				{#if destructive}<span data-slot="button-glyph" aria-hidden="true">×</span
					>{/if}{confirmLabel}
			</AlertDialog.Action>
		</div>
	</AlertDialog.Content>
</AlertDialog.Root>
