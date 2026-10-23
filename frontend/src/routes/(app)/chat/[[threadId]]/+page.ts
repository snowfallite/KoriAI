import { api, ok } from '$lib/api/client';
import type { ApiError } from '$lib/types';
import type { PageLoad } from './$types';
import type { Thread } from './logic';

export type ChatState =
	| { kind: 'new' }
	| { kind: 'ready'; thread: Thread }
	| { kind: 'missing' }
	| { kind: 'error'; error: ApiError };

async function fetchThread(threadId: string): Promise<ChatState> {
	try {
		const path = { thread_id: threadId };
		const thread = await ok(api.GET('/api/chat/threads/{thread_id}', { params: { path } }));
		return { kind: 'ready', thread };
	} catch (error) {
		const failure = error as ApiError;
		// A thread of someone else looks missing (tech.md §6.5); so does an address with no id.
		if (failure.code === 'not_found' || failure.code === 'validation_error') {
			return { kind: 'missing' };
		}
		return { kind: 'error', error: failure };
	}
}

export const load: PageLoad = async ({ params, url, depends }) => {
	depends('app:chat');
	// /chat?q=… puts the question in the field and sends nothing (F-03 AC 10).
	const question = url.searchParams.get('q') ?? '';
	const chat: ChatState = params.threadId ? await fetchThread(params.threadId) : { kind: 'new' };
	return { question, chat };
};
