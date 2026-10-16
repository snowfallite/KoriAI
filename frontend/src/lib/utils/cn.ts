import { createCn } from 'cn/config';
import { defaultConfig } from 'tailwind-variants';

// The type scale of tech.md §13.3 (app.css): text-ui and its kin set the font size. Unknown to
// the merge tables, they would pass for text colors and knock out text-background, or the other
// way round.
const TYPE_SCALE = {
	extend: {
		classGroups: {
			'font-size': [
				{ text: ['hero', 'display', 'quote', 'title', 'lead', 'body', 'ui', 'caps', 'caption'] }
			]
		}
	}
};

export const cn = createCn(TYPE_SCALE);

// tailwind-variants merges the variants of the primitives with its own engine and reads this
// config when a primitive calls tv(); every primitive imports this module before that call.
defaultConfig.twMergeConfig = TYPE_SCALE;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type WithoutChild<T> = T extends { child?: any } ? Omit<T, 'child'> : T;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type WithoutChildren<T> = T extends { children?: any } ? Omit<T, 'children'> : T;
export type WithoutChildrenOrChild<T> = WithoutChildren<WithoutChild<T>>;
export type WithElementRef<T, U extends HTMLElement = HTMLElement> = T & { ref?: U | null };
