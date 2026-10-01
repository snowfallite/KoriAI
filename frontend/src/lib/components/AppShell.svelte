<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import type { NavItem } from '$lib/nav';
	import type { UserOut } from '$lib/types';
	import * as Sidebar from '$lib/ui/sidebar';
	import Logo from './Logo.svelte';
	import ThemeToggle from './ThemeToggle.svelte';

	let { nav, user, children }: { nav: NavItem[]; user: UserOut; children: Snippet } = $props();

	const current = (item: NavItem) =>
		page.url.pathname === item.href || page.url.pathname.startsWith(`${item.href}/`);
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- NAV holds app paths; the SPA has no base path -->

<!-- A 240 px sidebar on the desktop, four tabs at the bottom under 768 px (tech.md §13.3). -->
<Sidebar.Provider style="--sidebar-width: 15rem">
	<Sidebar.Root collapsible="none" class="sticky top-0 hidden h-svh border-r md:flex">
		<Sidebar.Header class="h-12 justify-center border-b px-4"><Logo /></Sidebar.Header>
		<Sidebar.Content>
			<Sidebar.Group>
				<Sidebar.Menu>
					{#each nav as item (item.id)}
						<Sidebar.MenuItem>
							<!-- Kïoku links: caps in ink-muted, red on hover, the current one a red plate. -->
							<Sidebar.MenuButton
								isActive={current(item) || undefined}
								class="tracking-wider text-muted-foreground uppercase hover:bg-transparent hover:text-primary data-[active=true]:bg-primary data-[active=true]:text-primary-foreground"
							>
								{#snippet child({ props })}
									<a href={item.href} aria-current={current(item) ? 'page' : undefined} {...props}>
										<item.icon />
										<span>{item.label}</span>
									</a>
								{/snippet}
							</Sidebar.MenuButton>
						</Sidebar.MenuItem>
					{/each}
				</Sidebar.Menu>
			</Sidebar.Group>
		</Sidebar.Content>
		<Sidebar.Footer class="border-t px-4 py-3 text-xs">
			<p class="truncate">{user.display_name ?? user.email}</p>
			{#if user.display_name}
				<p class="truncate text-muted-foreground">{user.email}</p>
			{/if}
		</Sidebar.Footer>
	</Sidebar.Root>

	<div class="flex min-w-0 flex-1 flex-col">
		<header
			class="sticky top-0 z-10 flex h-12 items-center justify-between border-b bg-background px-4"
		>
			<div class="md:invisible"><Logo /></div>
			<ThemeToggle />
		</header>
		<main class="mx-auto w-full max-w-[1200px] flex-1 px-4 pt-6 pb-24 md:pb-6">
			{@render children()}
		</main>
	</div>

	<nav
		aria-label="Разделы"
		class="fixed inset-x-0 bottom-0 z-20 grid auto-cols-fr grid-flow-col border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
	>
		{#each nav as item (item.id)}
			<a
				href={item.href}
				aria-current={current(item) ? 'page' : undefined}
				class="flex flex-col items-center gap-1 py-2 text-[11px] tracking-wider text-muted-foreground uppercase aria-[current=page]:bg-primary aria-[current=page]:text-primary-foreground"
			>
				<item.icon class="size-5" />
				{item.label}
			</a>
		{/each}
	</nav>
</Sidebar.Provider>
