import BriefcaseBusiness from '@lucide/svelte/icons/briefcase-business';
import History from '@lucide/svelte/icons/history';
import MessageSquare from '@lucide/svelte/icons/message-square';
import Settings from '@lucide/svelte/icons/settings';
import type { Component } from 'svelte';

export interface NavItem {
	id: 'chat' | 'history' | 'portfolio' | 'settings';
	label: string;
	href: string;
	icon: Component<{ class?: string }>;
}

/** The tabs of the app in their order (tech.md §1, §13.2). */
export const NAV: NavItem[] = [
	{ id: 'chat', label: 'Чат', href: '/chat', icon: MessageSquare },
	{ id: 'history', label: 'История', href: '/history', icon: History },
	{ id: 'portfolio', label: 'Портфель', href: '/portfolio', icon: BriefcaseBusiness },
	{ id: 'settings', label: 'Настройки', href: '/settings', icon: Settings }
];
