// Pure logic of the sign-in pages (tech.md §16.2): where an error of the API shows, and the
// candles of the scene «свет над графиком» (docs/ui-references/kori-v4).
import type { ApiError } from '$lib/types';

export type Field = 'email' | 'password' | 'invite' | 'name';

// Errors of the auth contract (tech.md §6.2) that belong to one field.
const BY_CODE: Partial<Record<ApiError['code'], Field>> = {
	invalid_credentials: 'password',
	email_taken: 'email',
	invite_required: 'invite',
	invite_invalid: 'invite'
};

// A validation error names the field of the body it failed on.
const BY_KEY: Record<string, Field> = {
	email: 'email',
	password: 'password',
	invite_code: 'invite',
	display_name: 'name'
};

const CHECK: Record<Field, string> = {
	email: 'Проверьте email',
	password: 'Не короче 10 символов',
	invite: 'Проверьте код приглашения',
	name: 'Проверьте имя'
};

/** The field an error of the API belongs to and the line to show there; null for an error of
 * the whole form, such as a closed registration or too many attempts. */
export function fieldError(error: ApiError): { field: Field; message: string } | null {
	const field = BY_CODE[error.code];
	if (field) return { field, message: error.message };
	if (error.code !== 'validation_error') return null;
	const errors = error.details?.errors;
	if (!Array.isArray(errors)) return null;
	for (const entry of errors as { loc?: unknown }[]) {
		const key = Array.isArray(entry?.loc) ? entry.loc.at(-1) : undefined;
		const found = typeof key === 'string' ? BY_KEY[key] : undefined;
		if (found) return { field: found, message: CHECK[found] };
	}
	return null;
}

/** A Japanese candle of the scene in its 1440 × 900 box: the left edge of the column, the open
 * and the close of the body, the ends of the wicks. y grows downwards, so a rise closes above. */
export interface Candle {
	x: number;
	open: number;
	close: number;
	high: number;
	low: number;
}

// The chart of html/login.html: 30 columns 48 px apart, bodies 34 px wide and a whole number of
// 28 px high, a path from y 616 up to y 168 with the peak under the glow.
const PATH: [x: number, open: number, close: number, high: number, low: number][] = [
	[7, 616, 532, 518, 616],
	[55, 532, 448, 392, 532],
	[103, 448, 504, 420, 518],
	[151, 504, 560, 448, 588],
	[199, 560, 644, 504, 644],
	[247, 644, 588, 546, 686],
	[295, 588, 532, 476, 588],
	[343, 532, 476, 420, 574],
	[391, 476, 532, 462, 532],
	[439, 532, 476, 462, 574],
	[487, 476, 420, 378, 490],
	[535, 420, 476, 364, 504],
	[583, 476, 532, 434, 574],
	[631, 532, 476, 420, 560],
	[679, 476, 420, 406, 490],
	[727, 420, 364, 336, 448],
	[775, 364, 448, 308, 462],
	[823, 448, 392, 378, 462],
	[871, 392, 336, 294, 406],
	[919, 336, 252, 238, 364],
	[967, 252, 336, 224, 364],
	[1015, 336, 252, 238, 364],
	[1063, 252, 168, 112, 294],
	[1111, 168, 84, 56, 182],
	[1159, 84, 168, 28, 182],
	[1207, 168, 84, 42, 210],
	[1255, 84, 140, 56, 154],
	[1303, 140, 196, 126, 196],
	[1351, 196, 112, 70, 210],
	[1399, 112, 168, 56, 210]
];

export const CANDLES: Candle[] = PATH.map(([x, open, close, high, low]) => ({
	x,
	open,
	close,
	high,
	low
}));

const BODY = 34;

export interface CandleShape {
	rise: boolean;
	body: { x: number; y: number; width: number; height: number };
	wicks: { x: number; y1: number; y2: number }[];
}

/** A candle as the mockup draws it: a rise as a hollow frame of 1 px (its rect sits half a pixel
 * in), a fall as a filled body; the wicks run outside the body only, the upper one of a rise up
 * to the line of its frame. */
export function candleShapes({ x, open, close, high, low }: Candle): CandleShape {
	const rise = close < open;
	const top = Math.min(open, close);
	const bottom = Math.max(open, close);
	const middle = x + BODY / 2 + 0.5;
	const wicks: CandleShape['wicks'] = [];
	if (high < top) wicks.push({ x: middle, y1: high, y2: rise ? top + 1 : top });
	if (low > bottom) wicks.push({ x: middle, y1: bottom, y2: low });
	const body = rise
		? { x: x + 0.5, y: top + 0.5, width: BODY - 1, height: bottom - top - 1 }
		: { x, y: top, width: BODY, height: bottom - top };
	return { rise, body, wicks };
}
