import type { components } from '$lib/api/schema';

type Schemas = components['schemas'];

export type StreamEvent = Schemas['StreamEvent'];
export type ArtifactOut = Schemas['ArtifactOut'];
export type ChartSpec = Schemas['ChartSpec'];
export type TableSpec = Schemas['TableSpec'];
export type ImageSpec = Schemas['ImageSpec'];
export type SourceRef = Schemas['SourceRef'];
export type InstrumentBrief = Schemas['InstrumentBrief'];

/** The only hand-written API type: client.ts throws it (tech.md §12.1). */
export type ApiError = Schemas['ErrorOut'] & { status: number };
