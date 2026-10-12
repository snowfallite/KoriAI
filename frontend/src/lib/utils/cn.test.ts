import { describe, expect, it } from 'vitest';
import { cn } from './cn';

describe('cn', () => {
	it('keeps a size of the type scale next to a text color', () => {
		expect(cn('text-ui bg-foreground text-background')).toBe(
			'text-ui bg-foreground text-background'
		);
		expect(cn('text-caps text-muted-foreground', 'text-caption')).toBe(
			'text-muted-foreground text-caption'
		);
	});

	it('lets a later size of the scale win over an earlier one', () => {
		expect(cn('text-ui', 'text-lead')).toBe('text-lead');
		expect(cn('text-ui', 'text-[14px]')).toBe('text-[14px]');
	});
});
