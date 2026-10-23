import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import {
	MAX_QUESTION,
	canSend,
	copyText,
	greeting,
	isOver,
	questionCount,
	runFailure,
	runLabel,
	seconds,
	sendsOnKey,
	threadTitle,
	took,
	turns,
	type Message,
	type Thread
} from './logic';

function message(role: Message['role'], content: string, at = '2026-10-22T16:04:00Z'): Message {
	return {
		id: `${role}-${content}`,
		role,
		status: 'complete',
		content,
		blocks: [{ type: 'markdown', text: content }],
		artifacts: [],
		sources: [],
		meta: {
			model_family: null,
			model_id: null,
			routing_reason: null,
			warnings: [],
			ungrounded_numbers: [],
			disclaimer: false,
			tokens_billable: null,
			web_credits: null,
			tools: []
		},
		created_at: at
	};
}

function thread(title: string | null, messages: Message[]): Thread {
	return {
		thread: {
			id: 't1',
			title,
			title_source: 'auto',
			message_count: messages.length,
			last_message_at: null,
			archived: false,
			created_at: '2026-10-22T16:00:00Z',
			snippet: null
		},
		messages,
		active_run: null
	};
}

describe('canSend', () => {
	it('sends a question with words in it and nothing blank (F-03 AC 8)', () => {
		expect(canSend('Что такое дюрация?')).toBe(true);
		expect(canSend('')).toBe(false);
		expect(canSend('  \n\t ')).toBe(false);
	});

	it('holds a question to 4000 characters', () => {
		expect(canSend('я'.repeat(MAX_QUESTION))).toBe(true);
		expect(canSend('я'.repeat(MAX_QUESTION + 1))).toBe(false);
		expect(canSend(` ${'я'.repeat(MAX_QUESTION)} `)).toBe(true);
	});
});

describe('sendsOnKey', () => {
	it('sends on Enter and breaks the line on Shift+Enter (F-03 AC 8)', () => {
		expect(sendsOnKey({ key: 'Enter', shiftKey: false, isComposing: false })).toBe(true);
		expect(sendsOnKey({ key: 'Enter', shiftKey: true, isComposing: false })).toBe(false);
	});

	it('lets Enter finish a composition and ignores other keys', () => {
		expect(sendsOnKey({ key: 'Enter', shiftKey: false, isComposing: true })).toBe(false);
		expect(sendsOnKey({ key: 'a', shiftKey: false, isComposing: false })).toBe(false);
	});
});

describe('turns', () => {
	it('numbers the questions and pairs each with the answer after it', () => {
		const q1 = message('user', 'Раз');
		const a1 = message('assistant', 'Ответ раз');
		const q2 = message('user', 'Два');
		const a2 = message('assistant', 'Ответ два');
		const q3 = message('user', 'Три');

		expect(turns([q1, a1, q2, a2, q3])).toEqual([
			{ number: 1, question: q1, answer: a1 },
			{ number: 2, question: q2, answer: a2 },
			{ number: 3, question: q3, answer: null }
		]);
	});

	it('gives every question one turn in order', () => {
		const roles = fc.array(fc.constantFrom<Message['role']>('user', 'assistant'), {
			maxLength: 20
		});
		fc.assert(
			fc.property(roles, (list) => {
				const messages = list.map((role, n) => message(role, String(n)));
				const found = turns(messages);
				const questions = messages.filter((m) => m.role === 'user');

				expect(found.map((turn) => turn.question)).toEqual(questions);
				expect(found.map((turn) => turn.number)).toEqual(questions.map((_, n) => n + 1));
				for (const turn of found) {
					const next = messages[messages.indexOf(turn.question) + 1];
					expect(turn.answer).toBe(next?.role === 'assistant' ? next : null);
				}
			})
		);
	});
});

describe('the header of a thread', () => {
	it('names a thread by its title, else by its first question', () => {
		const messages = [message('user', 'Что с портфелем?'), message('assistant', 'Всё хорошо')];

		expect(threadTitle(thread('Портфель', messages))).toBe('Портфель');
		expect(threadTitle(thread(null, messages))).toBe('Что с портфелем?');
	});

	it('cuts a long first question to one line of the header', () => {
		const long = `Расскажи\nподробно ${'о портфеле '.repeat(20)}`;

		const title = threadTitle(thread(null, [message('user', long)]));

		expect(title.length).toBeLessThanOrEqual(80);
		expect(title.startsWith('Расскажи подробно о портфеле')).toBe(true);
		expect(title.endsWith('…')).toBe(true);
	});

	it('counts the questions in Russian', () => {
		expect([1, 2, 5, 11, 21, 22].map(questionCount)).toEqual([
			'1 вопрос',
			'2 вопроса',
			'5 вопросов',
			'11 вопросов',
			'21 вопрос',
			'22 вопроса'
		]);
	});
});

describe('greeting', () => {
	it('greets by the hour in Moscow', () => {
		// UTC + 3: 06:00 is 09:00, 10:00 is 13:00, 16:00 is 19:00, 22:30 is 01:30.
		expect(greeting(new Date('2026-10-22T06:00:00Z'), 'Демо')).toBe('Доброе утро, Демо');
		expect(greeting(new Date('2026-10-22T10:00:00Z'), 'Демо')).toBe('Добрый день, Демо');
		expect(greeting(new Date('2026-10-22T16:00:00Z'), 'Демо')).toBe('Добрый вечер, Демо');
		expect(greeting(new Date('2026-10-22T22:30:00Z'), 'Демо')).toBe('Доброй ночи, Демо');
	});

	it('goes without a name the user did not give', () => {
		expect(greeting(new Date('2026-10-22T16:00:00Z'), null)).toBe('Добрый вечер');
	});
});

describe('the time of a run', () => {
	it('tells seconds and minutes', () => {
		expect([0, 9, 59.9, 60, 125].map(seconds)).toEqual([
			'0 с',
			'9 с',
			'59 с',
			'1 мин 00 с',
			'2 мин 05 с'
		]);
		expect(seconds(-3)).toBe('0 с');
	});

	it('tells how long an answer took', () => {
		const question = message('user', 'Раз', '2026-10-22T16:04:00Z');
		const answer = message('assistant', 'Да', '2026-10-22T16:04:14.600Z');

		expect(took(question, answer)).toBe('14 с');
	});

	it('shows the place in the queue, then the step (F-03 AC 6)', () => {
		expect(runLabel({ position: 2, step: 0 }, 1)).toBe('В очереди: 2');
		expect(runLabel({ position: null, step: 0 }, 1)).toBe('Готовлю ответ');
		expect(runLabel({ position: null, step: 1 }, 9.7)).toBe('Шаг 1, 9 с');
	});

	it('knows a run is over once run.finished came', () => {
		expect(isOver({ status: 'queued' })).toBe(false);
		expect(isOver({ status: 'running' })).toBe(false);
		for (const status of ['done', 'partial', 'cancelled', 'failed', 'interrupted'] as const) {
			expect(isOver({ status })).toBe(true);
		}
	});
});

describe('an answer', () => {
	it('copies its markdown without the artifacts', () => {
		const answer = {
			...message('assistant', 'x'),
			blocks: [
				{ type: 'markdown' as const, text: 'Итог.' },
				{ type: 'artifact' as const, artifact_id: 'a1' },
				{ type: 'markdown' as const, text: 'Детали.' }
			]
		};

		expect(copyText(answer)).toBe('Итог.\n\nДетали.');
	});

	it('shows the error of its run, or a general one after a reload (F-03 AC 5)', () => {
		const error = {
			code: 'llm_busy' as const,
			message: 'Модель не ответила, попробуйте ещё раз',
			details: null,
			request_id: 'r1'
		};

		expect(runFailure(error)).toEqual({ ...error, status: 0 });
		expect(runFailure(null)).toMatchObject({ message: 'Ответ не получен', request_id: '' });
	});
});
