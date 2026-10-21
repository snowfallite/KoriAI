// Pure logic of the error page (tech.md §13.3, S1-15 AC 8): what it says for an unknown address
// and for a failed load of the app.

// SvelteKit names an error it knows nothing about in English: such a title says nothing.
const STOCK = new Set(['Internal Error', 'Not Found', 'Error', '']);
const FAILED = 'Страница не загрузилась';

export interface ErrorView {
	title: string;
	text: string;
	/** An unknown address leads to the portfolio; a failed load offers Повторить. */
	missing: boolean;
	request_id: string | null;
}

export function errorView(status: number, error: App.Error | null, path: string): ErrorView {
	if (status === 404) {
		return {
			title: 'Страница не найдена',
			text: `По адресу ${path} ничего нет. Проверьте ссылку или вернитесь к портфелю.`,
			missing: true,
			request_id: null
		};
	}
	const message = error?.message.trim() ?? '';
	const title = STOCK.has(message) ? FAILED : message;
	const request_id = error?.request_id || null;
	const text = [
		title === FAILED ? null : `${FAILED}.`,
		'Проверьте интернет и повторите.',
		request_id ? 'Если не поможет, пришлите код запроса владельцу.' : null
	]
		.filter(Boolean)
		.join(' ');
	return { title, text, missing: false, request_id };
}
