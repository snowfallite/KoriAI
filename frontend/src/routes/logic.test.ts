import { describe, expect, it } from 'vitest';
import { errorView } from './logic';

// tech.md S1-15 AC 8 and docs/ui-references/kori-v4/html/error.html: the page says what happened
// in Russian instead of «404 Not Found» and «500 Internal Error».
describe('errorView', () => {
	it('names an unknown address and leads to the portfolio', () => {
		expect(errorView(404, { message: 'Not Found' }, '/no-such-page')).toEqual({
			title: 'Страница не найдена',
			text: 'По адресу /no-such-page ничего нет. Проверьте ссылку или вернитесь к портфелю.',
			missing: true,
			request_id: null
		});
	});

	it('gives the reason of a failed load and asks to send the request code', () => {
		const view = errorView(
			503,
			{ message: 'Нет связи с сервером', request_id: '0190a000-dead-7000-8000-0000000000ff' },
			'/portfolio'
		);

		expect(view).toEqual({
			title: 'Нет связи с сервером',
			text: 'Страница не загрузилась. Проверьте интернет и повторите. Если не поможет, пришлите код запроса владельцу.',
			missing: false,
			request_id: '0190a000-dead-7000-8000-0000000000ff'
		});
	});

	it('asks for no code when the error has none', () => {
		expect(errorView(503, { message: 'Нет связи с сервером' }, '/').text).toBe(
			'Страница не загрузилась. Проверьте интернет и повторите.'
		);
	});

	it('never shows the English title of an unexpected error', () => {
		for (const message of ['Internal Error', 'Error', '']) {
			const view = errorView(500, { message }, '/portfolio');

			expect(view.title).toBe('Страница не загрузилась');
			expect(view.text).toBe('Проверьте интернет и повторите.');
		}
	});
});
