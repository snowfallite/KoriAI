// Pure logic of the sign-in pages (tech.md §16.2): where an error of the API shows, and the
// caption under a new password.
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

const PLURAL = new Intl.PluralRules('ru-RU');
const SYMBOL: Record<string, string> = { one: 'символ', few: 'символа', many: 'символов' };

/** «12 символов · минимум 10»: the caption under a new password. */
export function lengthHint(length: number, min = 10): string {
	return `${length} ${SYMBOL[PLURAL.select(length)] ?? 'символа'} · минимум ${min}`;
}
