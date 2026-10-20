// @vitest-environment jsdom
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ConfirmDialog from './ConfirmDialog.svelte';

function open(destructive: boolean) {
	render(ConfirmDialog, {
		open: true,
		title: 'Удалить чат?',
		description: '«Что с моим портфелем и почему?» и 4 сообщения удалятся без возврата.',
		confirmLabel: destructive ? 'Удалить' : 'Подтвердить',
		destructive,
		onConfirm: vi.fn()
	});
	return screen.getByRole('alertdialog', { name: 'Удалить чат?' });
}

describe('ConfirmDialog', () => {
	// tech.md S1-15 AC 7: one × a dialog, at the action Удалить; Отмена and Esc close it.
	it('puts the only × on the delete action', () => {
		const dialog = open(true);
		const remove = screen.getByRole('button', { name: 'Удалить' });
		const cancel = screen.getByRole('button', { name: 'Отмена' });

		expect(dialog.textContent?.split('×')).toHaveLength(2);
		expect(remove.querySelector('[data-slot="button-glyph"]')?.textContent).toBe('×');
		expect(cancel.querySelector('[data-slot="button-glyph"]')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Закрыть' })).toBeNull();
	});

	it('confirms a harmless action without a glyph', () => {
		const dialog = open(false);

		expect(dialog.textContent).not.toMatch(/[×→]/);
		expect(screen.getByRole('button', { name: 'Подтвердить' })).toBeTruthy();
	});
});
