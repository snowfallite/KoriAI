// Pure logic of the settings tab (tech.md §16.2): the lines of the broker section and where an
// error of the API shows.
import type { components } from '$lib/api/schema';
import type { ApiError } from '$lib/types';
import { formatDate, formatNumber, formatTime } from '$lib/utils/format';

export type Connection = components['schemas']['BrokerConnectionOut'];
export type Account = Connection['accounts'][number];

/** The page of T-Invest on issuing a token. */
export const TOKEN_HELP = 'https://developer.tbank.ru/invest/intro/intro/token';

const PLURAL = new Intl.PluralRules('ru-RU');
const FOUND: Record<string, string> = { one: 'найден', few: 'найдено', many: 'найдено' };
const ACCOUNTS: Record<string, string> = { one: 'счёт', few: 'счёта', many: 'счетов' };

/** The note after a connection (kori-v4, Уведомления): «…, найдено 2 счёта». */
export function connectedNote(count: number): string {
	const form = PLURAL.select(count);
	const found = `${FOUND[form] ?? 'найдено'} ${formatNumber(count, 0)} ${ACCOUNTS[form] ?? 'счёта'}`;
	return `Т-Инвестиции подключены, ${found}`;
}

// The refusals of PUT /api/broker/connection (tech.md §6.3) that speak about the token itself.
const AT_FIELD = new Set<ApiError['code']>([
	'token_invalid',
	'token_not_read_only',
	'validation_error'
]);

/** The line under the token field; null for a failure of T-Invest or the server, which the
 * form shows above the field. */
export function tokenError(error: ApiError): string | null {
	return AT_FIELD.has(error.code) ? error.message : null;
}

/** The last check of the token in Moscow time. */
export function checkedAt(at: string | null): string {
	return at === null ? '—' : `${formatDate(at)}, ${formatTime(at)} МСК`;
}

const NOTES: Record<Account['status'], string | null> = {
	open: null,
	new: 'открывается',
	closed: 'закрыт',
	other: 'статус неизвестен'
};

/** What the name of an account leaves out: that it is not open. */
export function accountNote(status: Account['status']): string | null {
	return NOTES[status];
}
