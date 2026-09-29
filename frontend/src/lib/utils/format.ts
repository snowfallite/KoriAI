// Numbers and dates for people: ru-RU, Moscow time (tech.md §11, §13.3). Every function
// returns a string for any input: a dash stands for what cannot be shown.

type Numeric = string | number;
type DateLike = string | number | Date;

const DASH = '—';
const LOCALE = 'ru-RU';
// A DecimalStr of the API (§6.1): Intl formats it exactly, no float on the way.
const DECIMAL = /^-?\d+(\.\d+)?$/;
const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;
// ISO 8601 with a zone (§6.1); Date would also read '1,5' as a day of 2001.
const INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/i;

const numberFormats = new Map<string, Intl.NumberFormat>();

function numberFormat(options: Intl.NumberFormatOptions): Intl.NumberFormat {
	const key = JSON.stringify(options);
	let format = numberFormats.get(key);
	if (!format) {
		format = new Intl.NumberFormat(LOCALE, options);
		numberFormats.set(key, format);
	}
	return format;
}

/** The value Intl should format, or null when it is not a finite number. */
function numeric(value: unknown): string | number | null {
	if (typeof value === 'number') return Number.isFinite(value) ? value : null;
	if (typeof value !== 'string') return null;
	if (DECIMAL.test(value)) return value;
	const n = value.trim() === '' ? Number.NaN : Number(value);
	return Number.isFinite(n) ? n : null;
}

function format(value: unknown, options: Intl.NumberFormatOptions): string {
	const n = numeric(value);
	if (n === null) return DASH;
	try {
		// Intl reads a numeric string exactly; its types only list number and bigint.
		return numberFormat(options)
			.format(n as number)
			.replaceAll('-', '\u2212');
	} catch {
		return DASH;
	}
}

function sign(signed: boolean): Intl.NumberFormatOptions {
	// 'negative' hides the minus of a value that rounds to zero.
	return { signDisplay: signed ? 'exceptZero' : 'negative' };
}

function fraction(digits: number | undefined, fallback: number): Intl.NumberFormatOptions {
	if (digits === undefined || !Number.isFinite(digits)) return { maximumFractionDigits: fallback };
	const d = Math.min(Math.max(Math.trunc(digits), 0), 20);
	return { minimumFractionDigits: d, maximumFractionDigits: d };
}

/** Up to two decimals, or exactly `digits` of them. */
export function formatNumber(value: Numeric, digits?: number): string {
	return format(value, { ...fraction(digits, 2), ...sign(false) });
}

function knownCurrency(currency: unknown): currency is string {
	try {
		return typeof currency === 'string' && !!numberFormat({ style: 'currency', currency });
	} catch {
		return false; // Intl throws RangeError on a code it does not know
	}
}

export function formatMoney(
	amount: Numeric,
	currency: string,
	{ signed = false, compact = false }: { signed?: boolean; compact?: boolean } = {}
): string {
	const options: Intl.NumberFormatOptions = compact
		? { notation: 'compact', maximumSignificantDigits: 3, ...sign(signed) }
		: sign(signed);
	if (knownCurrency(currency)) return format(amount, { ...options, style: 'currency', currency });
	const number = format(amount, compact ? options : { ...options, ...fraction(2, 2) });
	return number === DASH || typeof currency !== 'string' ? number : `${number}\u00a0${currency}`;
}

/** A share (0.12) as percents (12,00 %). */
export function formatPercent(
	share: Numeric,
	{ signed = false, digits = 2 }: { signed?: boolean; digits?: number } = {}
): string {
	return format(share, { style: 'percent', ...fraction(digits, 2), ...sign(signed) });
}

/** Three significant digits with тыс., млн, млрд, трлн. */
export function formatCompact(value: Numeric): string {
	return format(value, { notation: 'compact', maximumSignificantDigits: 3, ...sign(false) });
}

const moscowParts = new Intl.DateTimeFormat('en-GB', {
	timeZone: 'Europe/Moscow',
	year: 'numeric',
	month: 'numeric',
	day: 'numeric'
});

/** Year, month and day in Moscow; a calendar date (YYYY-MM-DD) stays as it is. */
function moscowDay(value: unknown): [number, number, number] | null {
	if (typeof value === 'string') {
		const day = DAY.exec(value);
		if (day) return [Number(day[1]), Number(day[2]), Number(day[3])];
		if (!INSTANT.test(value)) return null;
	} else if (typeof value !== 'number' && !(value instanceof Date)) {
		return null;
	}
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return null;
	const parts = moscowParts.formatToParts(date);
	const part = (type: Intl.DateTimeFormatPartTypes) =>
		Number(parts.find((p) => p.type === type)?.value);
	return [part('year'), part('month'), part('day')];
}

const pad = (n: number) => String(n).padStart(2, '0');

function byDay(value: unknown, show: (year: number, month: number, day: number) => string) {
	const day = moscowDay(value);
	return day ? show(...day) : DASH;
}

/** dd.MM.yyyy */
export function formatDate(value: DateLike): string {
	return byDay(value, (year, month, day) => `${pad(day)}.${pad(month)}.${year}`);
}

/** MM.yyyy */
export function formatMonth(value: DateLike): string {
	return byDay(value, (year, month) => `${pad(month)}.${year}`);
}

/** 3 кв. 2026 */
export function formatQuarter(value: DateLike): string {
	return byDay(value, (year, month) => `${Math.ceil(month / 3)} кв. ${year}`);
}

export function formatYear(value: DateLike): string {
	return byDay(value, (year) => String(year));
}
