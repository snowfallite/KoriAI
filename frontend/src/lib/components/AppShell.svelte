<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import type { NavItem } from '$lib/nav';
	import { signOut } from '$lib/state/session.svelte';
	import type { UserOut } from '$lib/types';
	import { Button } from '$lib/ui/button';
	import * as Sidebar from '$lib/ui/sidebar';
	import { cn } from '$lib/utils/cn';
	import Logo from './Logo.svelte';
	import ThemeToggle from './ThemeToggle.svelte';

	let { nav, user, children }: { nav: NavItem[]; user: UserOut; children: Snippet } = $props();

	const current = (item: NavItem) =>
		page.url.pathname === item.href || page.url.pathname.startsWith(`${item.href}/`);
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -- NAV holds app paths; the SPA has no base path -->

<!-- A 240 px sidebar on the desktop, a header and four tabs at the bottom under 768 px
     (tech.md §13.3, docs/ui-references/kori-v3). -->
<Sidebar.Provider style="--sidebar-width: 15rem">
	<Sidebar.Root collapsible="none" class="sticky top-0 hidden h-svh shrink-0 border-r md:flex">
		<Sidebar.Header class="h-14 shrink-0 justify-center border-b px-5 py-0">
			<a href="/chat" class="w-max"><Logo /></a>
		</Sidebar.Header>
		<Sidebar.Content class="gap-0">
			<div class="p-5">
				<Button variant="secondary" href="/chat" class="w-full justify-start">
					<span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат
				</Button>
			</div>
			<nav aria-label="Разделы" class="pb-5">
				<Sidebar.Menu class="gap-0">
					{#each nav as item (item.id)}
						<Sidebar.MenuItem>
							<!-- Text in caps; the chosen item is white on the accent row with a red arrow. -->
							<Sidebar.MenuButton
								isActive={current(item) || undefined}
								class="h-9 gap-2 px-5 text-caps text-muted-foreground uppercase hover:bg-accent hover:text-foreground data-[active=true]:bg-accent data-[active=true]:text-foreground"
							>
								{#snippet child({ props })}
									<a href={item.href} aria-current={current(item) ? 'page' : undefined} {...props}>
										<!-- CSS draws the arrow: it stays out of the name and the text of the link. -->
										<span
											aria-hidden="true"
											class={cn(
												'w-3.5 shrink-0 text-ui tracking-normal text-primary',
												current(item) && "before:content-['→']"
											)}
										></span>
										<span>{item.label}</span>
									</a>
								{/snippet}
							</Sidebar.MenuButton>
						</Sidebar.MenuItem>
					{/each}
				</Sidebar.Menu>
			</nav>
		</Sidebar.Content>
		<Sidebar.Footer class="gap-3.5 border-t px-5 pt-4 pb-5">
			<div class="min-w-0">
				<p class="truncate text-ui">{user.display_name ?? user.email}</p>
				{#if user.display_name}
					<p class="truncate text-[11px]/4 text-grey-600">{user.email}</p>
				{/if}
			</div>
			<div class="flex items-center justify-between gap-2">
				<ThemeToggle />
				<Button variant="link" class="text-[10px]" onclick={signOut}>
					Выйти <span aria-hidden="true">→</span>
				</Button>
			</div>
		</Sidebar.Footer>
	</Sidebar.Root>

	<div class="flex min-w-0 flex-1 flex-col">
		<!-- A phone keeps the logo and a new chat on top; the theme and the exit live in Настройки. -->
		<header
			class="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b bg-background pr-1 pl-4 md:hidden"
		>
			<a href="/chat"><Logo /></a>
			<a href="/chat" aria-label="Новый чат" class="grid size-12 place-items-center text-[22px]">
				<span aria-hidden="true">+</span>
			</a>
		</header>
		<main class="flex-1 pb-16 md:pb-0">
			{@render children()}
		</main>
	</div>

	<nav
		aria-label="Разделы"
		class="fixed inset-x-0 bottom-0 z-20 grid h-16 grid-cols-4 border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
	>
		{#each nav as item (item.id)}
			<a
				href={item.href}
				aria-current={current(item) ? 'page' : undefined}
				class="relative flex flex-col items-center justify-center gap-1.5 text-[10px]/3 tracking-[0.08em] text-muted-foreground uppercase hover:text-foreground aria-[current=page]:text-foreground"
			>
				{#if current(item)}
					<span
						aria-hidden="true"
						class="absolute -top-px left-1/2 h-0.5 w-5 -translate-x-1/2 bg-primary"
					></span>
				{/if}
				<item.icon class="size-[18px]" />
				{item.label}
			</a>
		{/each}
	</nav>
</Sidebar.Provider>
