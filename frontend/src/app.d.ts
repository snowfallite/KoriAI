// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
import type { RowData } from '@tanstack/table-core';

declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

declare module '@tanstack/table-core' {
	// DataTable puts it on the header and the cells of the column: numbers align right.
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	interface ColumnMeta<TData extends RowData, TValue> {
		class?: string;
	}
}

export {};
