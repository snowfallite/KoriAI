// Pure logic of the chat tab (tech.md §16.2): what may be sent, the turns of a thread, the greeting
// and the fan of a new chat, the labels of a run.
import type { components } from '$lib/api/schema';
import type { ApiError } from '$lib/types';
import type { RunView } from '$lib/utils/stream-reducer';

export type Thread = components['schemas']['ThreadDetailOut'];
export type Message = components['schemas']['MessageOut'];
export type ErrorOut = components['schemas']['ErrorOut'];

/** The limit of a question (tech.md §6.5, MessageIn.text). */
export const MAX_QUESTION = 4000;

/** A question goes when it says something and fits the limit (F-03 AC 8). */
export function canSend(text: string): boolean {
	const question = text.trim();
	return question.length > 0 && question.length <= MAX_QUESTION;
}

/** Enter sends, Shift+Enter breaks the line, and the Enter that ends an IME composition only
 * ends it (F-03 AC 8). */
export function sendsOnKey(key: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'isComposing'>): boolean {
	return key.key === 'Enter' && !key.shiftKey && !key.isComposing;
}

export interface Turn {
	/** 1, 2, …: the number in the cell of the question strip */
	number: number;
	question: Message;
	/** null while the run goes, or when it ended without an answer */
	answer: Message | null;
}

/** The questions of a thread with their answers, in order. */
export function turns(messages: Message[]): Turn[] {
	const found: Turn[] = [];
	for (const message of messages) {
		const last = found.at(-1);
		if (message.role === 'user') {
			found.push({ number: found.length + 1, question: message, answer: null });
		} else if (last && last.answer === null) {
			last.answer = message;
		}
	}
	return found;
}

const TITLE = 80;

/** The name of a thread in its header: its title, else its first question (F-04 adds titles),
 * cut to one line of the header. */
export function threadTitle(thread: Thread): string {
	const first = thread.messages.find((message) => message.role === 'user');
	const title = (thread.thread.title ?? first?.content ?? 'Новый чат').replace(/\s+/g, ' ').trim();
	return title.length > TITLE ? `${title.slice(0, TITLE - 1).trimEnd()}…` : title;
}

const PLURAL = new Intl.PluralRules('ru-RU');
const QUESTIONS: Record<Intl.LDMLPluralRule, string> = {
	zero: 'вопросов',
	one: 'вопрос',
	two: 'вопроса',
	few: 'вопроса',
	many: 'вопросов',
	other: 'вопроса'
};

/** «2 вопроса» beside the title of a thread. */
export function questionCount(count: number): string {
	return `${count} ${QUESTIONS[PLURAL.select(count)]}`;
}

const HOUR = new Intl.DateTimeFormat('ru-RU', {
	hour: 'numeric',
	hourCycle: 'h23',
	timeZone: 'Europe/Moscow'
});

/** «Добрый вечер, Демо» over a new chat, by Moscow time (kori-v4, Чат: начало). */
export function greeting(now: Date, name: string | null): string {
	const hour = Number(HOUR.format(now));
	const part =
		hour < 5
			? 'Доброй ночи'
			: hour < 12
				? 'Доброе утро'
				: hour < 18
					? 'Добрый день'
					: 'Добрый вечер';
	return name ? `${part}, ${name}` : part;
}

export interface Suggestion {
	/** The data that answers it: the ray of the fan leads there (tech.md §13.3) */
	source: string;
	question: string;
}

/** The fan of a new chat: the first one is the recommended path. No numbers here: a question
 * of the fan states nothing about the portfolio of the reader. */
export const SUGGESTIONS: Suggestion[] = [
	{ source: 'Портфель', question: 'Обзор портфеля: структура и вклад позиций' },
	{ source: 'Рынок, веб', question: 'Что двигало ценой Газпрома за месяц' },
	{ source: 'Портфель', question: 'Дивиденды и купоны до конца года' },
	{ source: 'Рынок', question: 'SBER, T и MOEX: доходность и риск за год' },
	{ source: 'Отчётность', question: 'МСФО ЛУКОЙЛа: выручка и долг за 5 лет' }
];

/** «9 с», «2 мин 05 с». */
export function seconds(total: number): string {
	const whole = Math.max(0, Math.floor(total));
	if (whole < 60) return `${whole} с`;
	return `${Math.floor(whole / 60)} мин ${String(whole % 60).padStart(2, '0')} с`;
}

/** How long the answer took: from the question to the answer. */
export function took(question: Message, answer: Message): string {
	return seconds((Date.parse(answer.created_at) - Date.parse(question.created_at)) / 1000);
}

/** The right side of the strip of a running question: the place in the queue, or the step and
 * the time since the question (F-03 AC 6). */
export function runLabel(run: Pick<RunView, 'position' | 'step'>, elapsed: number): string {
	if (run.position !== null) return `В очереди: ${run.position}`;
	if (run.step === 0) return 'Готовлю ответ';
	return `Шаг ${run.step}, ${seconds(elapsed)}`;
}

/** The run is over: run.finished came (tech.md §7). */
export function isOver(run: Pick<RunView, 'status'>): boolean {
	return run.status !== 'queued' && run.status !== 'running';
}

/** The text of an answer to copy: its markdown, without the artifacts. */
export function copyText(answer: Message): string {
	return answer.blocks
		.flatMap((block) => (block.type === 'markdown' ? [block.text] : []))
		.join('\n\n');
}

/** An error of a failed run as ErrorState shows it (F-03 AC 5); after a reload the thread
 * keeps only the failed answer, so the message is a general one. */
export function runFailure(error: ErrorOut | null | undefined): ApiError {
	if (error) return { ...error, status: 0 };
	return {
		code: 'internal',
		message: 'Ответ не получен',
		details: null,
		request_id: '',
		status: 0
	};
}
