import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import vectors from '../../../../backend/fixtures/seed/blocks_cases.json';
import { splitBlocks } from './blocks';

// The same vectors drive split_blocks of the backend (tech.md §9.9, §11).
const PLACEHOLDER = /^\s*\[\[([cti][0-9]+)\]\]\s*$/;
const POOL = ['c1', 'c2', 'c10', 't1', 't2', 'i1'];
const UNKNOWN = ['c9', 't7', 'i4'];
const ID = new Map(
	POOL.map((localId, n) => [localId, `01920000-0000-7000-8000-${String(n).padStart(12, '0')}`])
);

const placeholderLines = fc
	.tuple(
		fc.constantFrom('', ' ', '  ', '\t'),
		fc.constantFrom(...POOL, ...UNKNOWN),
		fc.constantFrom('', ' ', '\t')
	)
	.map(([pad, localId, tail]) => `${pad}[[${localId}]]${tail}`);
const texts = fc
	.array(fc.oneof(placeholderLines, fc.string({ maxLength: 40 })), { maxLength: 12 })
	.map((lines) => lines.join('\n'));
// The artifacts of a run in creation order.
const runs = fc
	.uniqueArray(fc.constantFrom(...POOL))
	.map((ids) => new Map(ids.map((localId) => [localId, ID.get(localId) ?? ''])));

/** Placeholder ids of the text in the order of their first line. */
function placed(text: string): string[] {
	const found = text.split('\n').flatMap((line) => PLACEHOLDER.exec(line)?.[1] ?? []);
	return [...new Set(found)];
}

describe('splitBlocks', () => {
	it.each(vectors.cases)('follows the shared vector: $name', (vector) => {
		const known = new Map(vector.artifacts.map((artifact) => [artifact.local_id, artifact.id]));

		const found = splitBlocks(vector.text, known);

		expect(found.blocks).toEqual(vector.blocks);
		expect(found.unknown).toEqual(vector.unknown);
	});

	it('leaves no placeholder line in a block', () => {
		fc.assert(
			fc.property(texts, runs, (text, known) => {
				for (const block of splitBlocks(text, known).blocks) {
					if (block.type !== 'markdown') continue;
					expect(block.text).toBe(block.text.trim());
					expect(block.text).not.toBe('');
					expect(block.text.split('\n').some((line) => PLACEHOLDER.test(line))).toBe(false);
				}
			})
		);
	});

	it('shows every artifact once, placed ones first, the rest in creation order', () => {
		fc.assert(
			fc.property(texts, runs, (text, known) => {
				const shown = splitBlocks(text, known).blocks.flatMap((block) =>
					block.type === 'artifact' ? [block.artifact_id] : []
				);

				const inText = placed(text).filter((localId) => known.has(localId));
				const rest = [...known.keys()].filter((localId) => !inText.includes(localId));
				expect(shown).toEqual([...inText, ...rest].map((localId) => known.get(localId)));
			})
		);
	});

	it('lists each missing placeholder once', () => {
		fc.assert(
			fc.property(texts, runs, (text, known) => {
				expect(splitBlocks(text, known).unknown).toEqual(
					placed(text).filter((localId) => !known.has(localId))
				);
			})
		);
	});

	it('splits any text', () => {
		fc.assert(
			fc.property(fc.string(), runs, (text, known) => {
				expect(() => splitBlocks(text, known)).not.toThrow();
			})
		);
	});
});
