import type { components } from '$lib/api/schema';

type Schemas = components['schemas'];

export type StreamEvent = Schemas['StreamEvent'];

/** The only hand-written API type: client.ts throws it (tech.md §12.1). */
export type ApiError = Schemas['ErrorOut'] & { status: number };
