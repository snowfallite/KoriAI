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

<AlertDialog.Root bind:open>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title>{title}</AlertDialog.Title>
			{#if description}
				<AlertDialog.Description>{description}</AlertDialog.Description>
			{/if}
		</AlertDialog.Header>
		<AlertDialog.Footer>
			<AlertDialog.Cancel disabled={pending}>Отмена</AlertDialog.Cancel>
			<AlertDialog.Action
				variant={destructive ? 'destructive' : 'default'}
				disabled={pending}
				onclick={confirm}
			>
				{confirmLabel}
			</AlertDialog.Action>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>
