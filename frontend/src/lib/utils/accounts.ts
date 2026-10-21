// How the interface calls a broker account (tech.md §13.3): by its name. The alias acc1 keeps the
// account out of the LLM context and the URL short (§3.5), so it never shows.

/** The label of each account by its alias: its name, a number after a repeated one
 * («Брокерский счёт (2)») in the order of the accounts. Every label is unique. */
export function accountNames(accounts: { alias: string; name: string }[]): Map<string, string> {
	const labels = new Map<string, string>();
	const taken = new Set<string>();
	for (const { alias, name } of accounts) {
		let label = name;
		for (let n = 2; taken.has(label); n++) label = `${name} (${n})`;
		taken.add(label);
		labels.set(alias, label);
	}
	return labels;
}
