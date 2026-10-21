// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { ApiError } from '$lib/types';
import ErrorState from './ErrorState.svelte';

const ERROR: ApiError = {
	code: 'tinvest_unavailable',
	message: 'Т-Инвестиции не отвечают, попробуйте позже',
	details: null,
	request_id: '0190a000-dead-7000-8000-0000000000ff',
	status: 503
};

describe('ErrorState', () => {
	// tech.md S1-15 AC 7: a failed load wears a red-deep bar, never a × cell that reads as «close».
	it('shows the message without a ×', () => {
		render(ErrorState, { error: ERROR, onRetry: vi.fn() });
		const alert = screen.getByRole('alert');

		expect(alert.textContent).toContain('Т-Инвестиции не отвечают, попробуйте позже');
		expect(alert.textContent).not.toContain('×');
	});

	it('gives the request code in normal case with a way to copy it', () => {
		render(ErrorState, { error: ERROR });
		const alert = screen.getByRole('alert');

		expect(alert.textContent).toContain('Код запроса 0190a000-dead-7000-8000-0000000000ff');
		expect(screen.getByRole('button', { name: 'Копировать код запроса' })).toBeTruthy();
		expect(alert.querySelector('.uppercase')).toBeNull();
	});

	it('leaves the code out when the error has none', () => {
		render(ErrorState, { error: { ...ERROR, request_id: '' } });

		expect(screen.getByRole('alert').textContent).not.toContain('Код запроса');
		expect(screen.queryByRole('button', { name: 'Копировать код запроса' })).toBeNull();
	});

	it('retries on Повторить', async () => {
		const onRetry = vi.fn();
		render(ErrorState, { error: ERROR, onRetry });

		await fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));

		expect(onRetry).toHaveBeenCalledOnce();
	});
});
