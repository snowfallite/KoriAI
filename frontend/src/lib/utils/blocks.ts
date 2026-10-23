import type { components } from '$lib/api/schema';

type MessageBlock = components['schemas']['MessageBlock'];

export interface Split {
	blocks: MessageBlock[];
	/** Placeholders without an artifact of the run, each once */
	unknown: string[];
}

/** A line with nothing but an artifact placeholder (tech.md §9.9). */
const PLACEHOLDER = /^\s*\[\[([cti][0-9]+)\]\]\s*$/;

/**
 * Pure. The answer as markdown and artifact blocks in the order of the text, the way split_blocks
 * of the backend builds them after the run (tech.md §9.9); both pass seed/blocks_cases.json. The
 * stream needs it before the answer is saved.
 *
 * `known` maps the local ids of the artifacts of the run to their ids in creation order. Every
 * placeholder line ends a markdown block; an unknown or repeated one shows nothing, and the
 * artifacts the text leaves out follow it in creation order.
 */
export function splitBlocks(text: string, known: ReadonlyMap<string, string>): Split {
	const blocks: MessageBlock[] = [];
	const unknown: string[] = [];
	const shown = new Set<string>();
	let lines: string[] = [];

	const closeMarkdown = () => {
		const part = lines.join('\n').trim();
		lines = [];
		if (part) blocks.push({ type: 'markdown', text: part });
	};

	// Only \n: the backend splits the same way.
	for (const line of text.split('\n')) {
		const localId = PLACEHOLDER.exec(line)?.[1];
		if (localId === undefined) {
			lines.push(line);
			continue;
		}
		closeMarkdown();
		const artifactId = known.get(localId);
		if (artifactId === undefined) {
			if (!unknown.includes(localId)) unknown.push(localId);
		} else if (!shown.has(localId)) {
			shown.add(localId);
			blocks.push({ type: 'artifact', artifact_id: artifactId });
		}
	}
	closeMarkdown();
	for (const [localId, artifactId] of known) {
		if (!shown.has(localId)) blocks.push({ type: 'artifact', artifact_id: artifactId });
	}
	return { blocks, unknown };
}
