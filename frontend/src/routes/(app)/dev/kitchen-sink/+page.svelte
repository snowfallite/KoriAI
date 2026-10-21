<script lang="ts">
	import Bold from '@lucide/svelte/icons/bold';
	import type { ColumnDef } from '@tanstack/table-core';
	import { onDestroy } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { api, ok } from '$lib/api/client';
	import AccountSelect from '$lib/components/AccountSelect.svelte';
	import AppShell from '$lib/components/AppShell.svelte';
	import ArtifactImage from '$lib/components/ArtifactImage.svelte';
	import ArtifactTable from '$lib/components/ArtifactTable.svelte';
	import ArtifactView from '$lib/components/ArtifactView.svelte';
	import ChartView from '$lib/components/ChartView.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import CopyButton from '$lib/components/CopyButton.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import Disclaimer from '$lib/components/Disclaimer.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorState from '$lib/components/ErrorState.svelte';
	import InstrumentBadge from '$lib/components/InstrumentBadge.svelte';
	import InstrumentLogo from '$lib/components/InstrumentLogo.svelte';
	import LoadingBlock from '$lib/components/LoadingBlock.svelte';
	import Logo from '$lib/components/Logo.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import MoneyText from '$lib/components/MoneyText.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import PercentText from '$lib/components/PercentText.svelte';
	import PeriodSelect from '$lib/components/PeriodSelect.svelte';
	import SourceList from '$lib/components/SourceList.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import UsageMeter from '$lib/components/UsageMeter.svelte';
	import { NAV } from '$lib/nav';
	import { LiveRun } from '$lib/state/run.svelte';
	import type { ApiError, InstrumentBrief, PeriodCode } from '$lib/types';
	import * as Alert from '$lib/ui/alert';
	import { Badge } from '$lib/ui/badge';
	import { Button, buttonVariants } from '$lib/ui/button';
	import * as Card from '$lib/ui/card';
	import { Checkbox } from '$lib/ui/checkbox';
	import * as Collapsible from '$lib/ui/collapsible';
	import * as Command from '$lib/ui/command';
	import * as Dialog from '$lib/ui/dialog';
	import * as DropdownMenu from '$lib/ui/dropdown-menu';
	import { Input } from '$lib/ui/input';
	import { Label } from '$lib/ui/label';
	import * as Popover from '$lib/ui/popover';
	import * as RadioGroup from '$lib/ui/radio-group';
	import { ScrollArea } from '$lib/ui/scroll-area';
	import { Separator } from '$lib/ui/separator';
	import * as Sheet from '$lib/ui/sheet';
	import { Switch } from '$lib/ui/switch';
	import * as Table from '$lib/ui/table';
	import * as Tabs from '$lib/ui/tabs';
	import { Textarea } from '$lib/ui/textarea';
	import { Toggle } from '$lib/ui/toggle';
	import * as ToggleGroup from '$lib/ui/toggle-group';
	import * as Tooltip from '$lib/ui/tooltip';
	import { accountNames } from '$lib/utils/accounts';
	import { cn } from '$lib/utils/cn';
	import { formatMoney, formatPercent } from '$lib/utils/format';
	import Demo from './components/Demo.svelte';
	import {
		ACCOUNTS,
		ARTIFACTS,
		CHARTS,
		ERROR,
		IMAGES,
		INSTRUMENTS,
		MANY_ACCOUNTS,
		MARKDOWN,
		SOURCES,
		TABLE,
		USER
	} from './fixtures';

	let account = $state<string | null>(null);
	let many = $state<string | null>('acc3');
	let period = $state<PeriodCode>('1y');
	let confirming = $state(false);
	let notify = $state(true);
	let agree = $state(false);
	let model = $state('auto');
	let style = $state('concise');
	let echo = $state<LiveRun | null>(null);
	const echoed = $derived(echo?.view.echo ? JSON.stringify(echo.view.echo) : null);
	onDestroy(() => echo?.close());

	// POST /api/dev/echo opens a stream of the user: dev.echo, then run.finished (tech.md §6.7).
	async function sendEcho() {
		echo?.close();
		const payload = { text: 'Привет, Kōri', sent_at: new Date().toISOString() };
		try {
			const { stream_id } = await ok(api.POST('/api/dev/echo', { body: { payload } }));
			echo = new LiveRun(stream_id);
		} catch (error) {
			toast.error((error as ApiError).message);
		}
	}

	const positions: ColumnDef<InstrumentBrief>[] = [
		{ accessorKey: 'ticker', header: 'Тикер' },
		{ accessorKey: 'name', header: 'Название' },
		{ accessorKey: 'instrument_type', header: 'Тип', enableSorting: false }
	];

	const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
	const LOGO_SIZES = [20, 24, 32, 48] as const;
	const GRADIENTS = [
		['ki-fade', 'красный к белому'],
		['ki-ignite', 'чёрный к красному'],
		['ki-ember', 'красный к бледно-красному'],
		['ki-hero', 'розовый, красный, чёрный'],
		['ki-tile', 'розовый, красный, серый']
	] as const;
	// The glyphs of v4 and what each says (tech.md §13.1): a cell only where the glyph means it.
	const GLYPHS = [
		[
			'→',
			'Действие вперёд',
			'Войти, отправить вопрос, спросить о портфеле',
			'bg-primary text-black'
		],
		['+', 'Создать', 'Новый чат, создать аккаунт', 'bg-grey-400 text-black'],
		['↓', 'Раскрыть', 'Выбор модели, шаги ответа', 'border border-grey-600'],
		[
			'×',
			'Прервать, удалить, закрыть',
			'Остановить ответ, удалить чат, закрыть окно',
			'bg-primary-deep text-primary-deep-foreground'
		],
		['↑↓', 'Порядок и направление', 'Сортировка колонки; рост или падение у итога портфеля', ''],
		['2', 'Номер', 'Номер вопроса в чате, счётчик у раздела: История¹²', 'bg-grey-400 text-black']
	] as const;
	// The sheet «Выбор» of v4: the menu, the model rows and the tabs of a phone.
	const MENU = ['Чат', 'История', 'Портфель', 'Настройки'];
	const MODELS = [
		['auto', 'Авто', 'подберёт модель по вопросу', 'сейчас'],
		['lite', 'Lite', 'короткие ответы и сводки', 'остаток 97 %'],
		['pro', 'Pro', 'анализ портфеля и бумаг', 'остаток 97 %'],
		['max', 'Max', 'отчётность МСФО и РСБУ', 'остаток 98 %']
	] as const;
	const HEADS = ['Инструмент', 'Счёт', 'Кол-во', 'Доля', 'Результат'];
	const SERIF = [
		'Главный минус даёт Газпром: −23 800 ₽, или −14,7 %, при доле 11,6 % портфеля. Числа внутри текста набраны моно: это данные, а не слова.',
		'',
		'> «Выручка Группы за отчётный год составила [ЧИСЛО] трлн ₽»: так выглядит цитата из отчёта МСФО'
	].join('\n');
	const chosen = (alias: string | null, list: typeof ACCOUNTS) =>
		alias === null ? 'все счета' : (accountNames(list).get(alias) ?? 'все счета');
	const [sber, gazp] = INSTRUMENTS as [InstrumentBrief, InstrumentBrief];
</script>

<PageHeader title="Kitchen sink" description="Примитивы §13.1 и компоненты §13.2 в текущей теме">
	{#snippet actions()}
		<ThemeToggle />
	{/snippet}
</PageHeader>

<div class="space-y-14 p-4 md:p-12">
	<section aria-label="Примитивы" class="space-y-4">
		<h2 class="border-b pb-3 text-[14px]/5 font-bold">Примитивы shadcn-svelte</h2>
		<div class="grid gap-8 md:grid-cols-2">
			<div class="flex flex-wrap items-center gap-2">
				<Badge>Подключены</Badge>
				<Badge variant="secondary">облигация</Badge>
				<Badge variant="outline">Брокерский</Badge>
				<Badge variant="destructive">ошибка</Badge>
				<Toggle aria-label="Жирный"><Bold /></Toggle>
			</div>
			<div class="space-y-3">
				<Label for="ks-search">Поиск по чатам</Label>
				<Input id="ks-search" placeholder="Например: дивиденды" />
				<Label for="ks-question">Вопрос</Label>
				<Textarea id="ks-question" placeholder="Что с моим портфелем?" />
			</div>
			<div class="space-y-3">
				<div class="flex items-center gap-3">
					<Checkbox id="ks-agree" bind:checked={agree} />
					<Label for="ks-agree">Показывать скрытые счета</Label>
				</div>
				<div class="flex flex-wrap items-center gap-2">
					<Dialog.Root>
						<Dialog.Trigger class={buttonVariants({ variant: 'outline' })}>Диалог</Dialog.Trigger>
						<Dialog.Content>
							<Dialog.Header>
								<Dialog.Title>Диалог</Dialog.Title>
								<Dialog.Description>Окно поверх страницы.</Dialog.Description>
							</Dialog.Header>
						</Dialog.Content>
					</Dialog.Root>
					<Sheet.Root>
						<Sheet.Trigger class={buttonVariants({ variant: 'outline' })}>Панель</Sheet.Trigger>
						<Sheet.Content>
							<Sheet.Header>
								<Sheet.Title>Панель</Sheet.Title>
								<Sheet.Description>Выезжает сбоку.</Sheet.Description>
							</Sheet.Header>
						</Sheet.Content>
					</Sheet.Root>
					<DropdownMenu.Root>
						<DropdownMenu.Trigger class={buttonVariants({ variant: 'outline' })}
							>Меню</DropdownMenu.Trigger
						>
						<DropdownMenu.Content>
							<DropdownMenu.Item>Переименовать</DropdownMenu.Item>
							<DropdownMenu.Separator />
							<DropdownMenu.Item variant="destructive">Удалить</DropdownMenu.Item>
						</DropdownMenu.Content>
					</DropdownMenu.Root>
					<Popover.Root>
						<Popover.Trigger class={buttonVariants({ variant: 'outline' })}>Поповер</Popover.Trigger
						>
						<Popover.Content>Подсказка с содержимым.</Popover.Content>
					</Popover.Root>
					<Tooltip.Provider>
						<Tooltip.Root>
							<Tooltip.Trigger class={buttonVariants({ variant: 'outline' })}
								>Тултип</Tooltip.Trigger
							>
							<Tooltip.Content>Короткая подсказка</Tooltip.Content>
						</Tooltip.Root>
					</Tooltip.Provider>
				</div>
			</div>
			<div class="space-y-3">
				<Collapsible.Root class="space-y-2">
					<Collapsible.Trigger class={buttonVariants({ variant: 'ghost', size: 'sm' })}>
						Как получен ответ <span aria-hidden="true">↓</span>
					</Collapsible.Trigger>
					<Collapsible.Content class="text-ui text-muted-foreground">
						Загрузил портфель, построил таблицу
					</Collapsible.Content>
				</Collapsible.Root>
				<ScrollArea class="h-24 border p-2 text-ui">
					{#each { length: 12 }, i (i)}
						<p>Строка {i + 1}</p>
					{/each}
				</ScrollArea>
			</div>
			<Card.Root>
				<Card.Header>
					<Card.Title>Карточка</Card.Title>
					<Card.Description>Рамка 1 px без заливки</Card.Description>
				</Card.Header>
				<Card.Content>Содержимое карточки.</Card.Content>
			</Card.Root>
			<Command.Root class="border">
				<Command.Input placeholder="Найти инструмент" />
				<Command.List>
					<Command.Empty>Ничего не найдено</Command.Empty>
					<Command.Group heading="Акции">
						{#each INSTRUMENTS as instrument (instrument.uid)}
							<Command.Item value={instrument.ticker}>{instrument.name}</Command.Item>
						{/each}
					</Command.Group>
				</Command.List>
			</Command.Root>
		</div>
		<Separator />
	</section>

	<Demo name="Глифы" note="глиф ставится, только когда говорит то, чего нет в подписи">
		<ul class="max-w-[640px] border-t text-ui">
			{#each GLYPHS as [glyph, meaning, where, cell] (meaning)}
				<li
					class="grid min-h-13 grid-cols-[40px_minmax(0,1fr)] items-center gap-x-4 border-b border-line-faint py-1.5 md:grid-cols-[40px_200px_minmax(0,1fr)]"
				>
					<span aria-hidden="true" class={cn('grid size-10 place-items-center text-base', cell)}
						>{glyph}</span
					>
					<span>{meaning}</span>
					<span class="col-start-2 text-muted-foreground md:col-start-3">{where}</span>
				</li>
			{/each}
		</ul>
		<p class="max-w-[640px] text-ui text-grey-600">
			Не ставим: стрелку в заголовке, стрелку после ссылки, крестик как знак ошибки, стрелку у
			каждой строки таблицы.
		</p>
	</Demo>

	<Demo
		name="Кнопки"
		note="ячейка-глиф у главного действия экрана и у действий с тем же смыслом; отмена, ссылки и второстепенное без ячейки"
	>
		<div class="flex flex-wrap items-center gap-x-5 gap-y-4">
			<Button><span data-slot="button-glyph" aria-hidden="true">→</span>Открыть настройки</Button>
			<Button variant="ai"
				><span data-slot="button-glyph" aria-hidden="true">→</span>Спросить о портфеле</Button
			>
			<Button variant="ai" size="icon" aria-label="Спросить">
				<span aria-hidden="true">→</span>
			</Button>
		</div>
		<div class="flex flex-wrap items-center gap-x-5 gap-y-4">
			<Button variant="secondary"
				><span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат</Button
			>
			<Button variant="outline">Повторить</Button>
			<Button variant="ghost">Отмена</Button>
			<Button variant="link">Выйти</Button>
			<Button disabled><span data-slot="button-glyph" aria-hidden="true">→</span>Недоступно</Button>
			<Button variant="link" disabled>Недоступно</Button>
		</div>
		<!-- On a white panel the ink label turns black (tech.md §13.1). -->
		<div class="theme-day flex flex-wrap gap-3 bg-background p-5">
			<p class="w-full text-caps text-grey-600">На белой панели: вход, регистрация, диалог</p>
			<Button size="lg"><span data-slot="button-glyph" aria-hidden="true">→</span>Войти</Button>
			<Button size="lg"
				><span data-slot="button-glyph" aria-hidden="true">+</span>Создать аккаунт</Button
			>
			<Button variant="destructive" size="lg"
				><span data-slot="button-glyph" aria-hidden="true">×</span>Удалить</Button
			>
			<Button variant="secondary" size="lg">Отмена</Button>
		</div>
	</Demo>

	<Demo name="Шрифты" note="моно звучит как интерфейс и данные, serif набирает то, что читают">
		<div class="grid gap-10 lg:grid-cols-2">
			<div class="space-y-2.5 border-t pt-5">
				<p class="text-caps text-grey-600">JetBrains Mono: интерфейс, числа, тикеры</p>
				<p class="text-[64px]/[64px] tracking-[-0.03em] whitespace-nowrap tabular-nums">
					1&nbsp;195&nbsp;145<span class="ml-3 text-[32px] tracking-normal text-grey-600">₽</span>
				</p>
				<p class="text-title">Позиции</p>
				<p class="text-[14px]/5 font-bold">Структура портфеля</p>
				<p class="text-ui text-prose">Брокерский, 846&nbsp;865&nbsp;₽, SBER, LKOH, ОФЗ 26240</p>
				<p class="text-caps text-grey-600">Цены Т-Инвестиций на 10.10.2026, 19:00 МСК</p>
			</div>
			<div class="space-y-4 border-t pt-5">
				<p class="text-caps text-grey-600">Noto Serif: ответ агента, цитаты из отчётов</p>
				<Markdown source={SERIF} />
				<p class="text-caps text-grey-600">Капс: только заголовки колонок таблиц</p>
				<Table.Root>
					<Table.Header>
						<Table.Row class="hover:bg-transparent">
							{#each HEADS as head (head)}
								<Table.Head>{head}</Table.Head>
							{/each}
						</Table.Row>
					</Table.Header>
				</Table.Root>
			</div>
		</div>
	</Demo>

	<Demo
		name="Выбранное"
		note="выбранное белое: в меню белый текст и красная полоса у края, инверсия в остальном"
	>
		<div class="grid gap-10 lg:grid-cols-2">
			<ul aria-label="Меню" class="w-60 border-y text-ui">
				{#each MENU as item, i (item)}
					<li
						class={cn(
							'relative flex h-9 items-center px-5',
							i === 2 ? 'bg-accent text-foreground' : 'text-foreground/54'
						)}
					>
						{#if i === 2}
							<span aria-hidden="true" class="absolute inset-y-0 left-0 w-0.5 bg-primary"></span>
						{/if}
						{item}
					</li>
				{/each}
			</ul>
			<div class="space-y-5">
				<Tabs.Root value="active">
					<Tabs.List>
						<Tabs.Trigger value="active">Активные</Tabs.Trigger>
						<Tabs.Trigger value="archive">Архив</Tabs.Trigger>
					</Tabs.List>
					<Tabs.Content value="active" class="text-ui">Чаты за неделю.</Tabs.Content>
					<Tabs.Content value="archive" class="text-ui">Архивные чаты.</Tabs.Content>
				</Tabs.Root>
				<ToggleGroup.Root
					type="single"
					variant="outline"
					size="sm"
					aria-label="Стиль ответа"
					bind:value={() => style, (next) => next && (style = next)}
				>
					<ToggleGroup.Item value="concise">Кратко</ToggleGroup.Item>
					<ToggleGroup.Item value="detailed">Подробно</ToggleGroup.Item>
				</ToggleGroup.Root>
				<div class="flex items-center gap-3">
					<Switch id="ks-notify" bind:checked={notify} />
					<Label for="ks-notify">Уведомления {notify ? 'включены' : 'выключены'}</Label>
				</div>
			</div>
			<RadioGroup.Root bind:value={model} aria-label="Модель" class="gap-0 border">
				{#each MODELS as [value, label, note, left] (value)}
					<Label
						class="flex h-13 cursor-pointer items-center gap-4 border-b border-line-faint px-4 text-ui last:border-0 hover:bg-accent has-data-checked:bg-foreground has-data-checked:text-background"
					>
						<RadioGroup.Item {value} />
						<span class="w-12">{label}</span>
						<span class="flex-1 opacity-70">{note}</span>
						<span class="text-caps">{left}</span>
					</Label>
				{/each}
			</RadioGroup.Root>
			<!-- The tabs of a phone: the chosen one white under a red line. -->
			<ul aria-label="Вкладки телефона" class="grid h-16 max-w-[390px] grid-cols-4 border">
				{#each NAV as item (item.id)}
					<li
						class={cn(
							'relative flex flex-col items-center justify-center gap-1.5 text-caption',
							item.id === 'chat' ? 'text-foreground' : 'text-muted-foreground'
						)}
					>
						{#if item.id === 'chat'}
							<span
								aria-hidden="true"
								class="absolute -top-px left-1/2 h-0.5 w-5 -translate-x-1/2 bg-primary"
							></span>
						{/if}
						<item.icon class="size-[18px]" />
						{item.label}
					</li>
				{/each}
			</ul>
		</div>
	</Demo>

	<Demo name="Карточки" note="рамка вместо заливки; сводка держится на числе">
		<div class="grid gap-12 xl:grid-cols-2">
			<section aria-labelledby="ks-broker" class="border">
				<header
					class="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b px-6 py-5"
				>
					<div class="space-y-1.5">
						<h3 id="ks-broker" class="text-ui font-bold">Т-Инвестиции</h3>
						<p class="text-[13px]/5 text-muted-foreground">2 счёта: Брокерский и ИИС</p>
					</div>
					<Badge>Подключены</Badge>
				</header>
				<dl
					class="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-6 gap-y-4 border-b border-line-faint px-6 py-5"
				>
					{#each [['Токен', 't.••••only'], ['Доступ', 'Только чтение'], ['Проверен', '10.10.2026, 09:00']] as [term, detail] (term)}
						<div>
							<dt class="text-caps text-grey-600">{term}</dt>
							<dd class="mt-1.5 text-[15px]/5">{detail}</dd>
						</div>
					{/each}
				</dl>
				<footer class="flex flex-wrap justify-end gap-3 px-6 py-4">
					<Button variant="outline">Проверить токен</Button>
					<Button variant="outline">Отключить</Button>
				</footer>
			</section>
			<div class="grid grid-cols-3 self-start">
				<StatCard
					label="Стоимость"
					value={formatMoney('1195145', 'RUB', { digits: 0 })}
					hint="все счета"
				/>
				<StatCard
					label="Результат"
					value={formatMoney('42090', 'RUB', { signed: true, digits: 0 })}
					delta={{ text: '+3,65 % к цене покупки', trend: 'up' }}
				/>
				<StatCard label="Позиции" value="10" hint="на 2 счетах" />
			</div>
		</div>
	</Demo>

	<Demo
		name="Уведомления"
		note="вид сообщает полоса слева и сам текст: ошибка, понижение, готово, справка"
	>
		<div class="grid max-w-[640px] gap-2">
			<Alert.Root variant="destructive">
				<Alert.Title>Т-Инвестиции не отвечают. Повторите позже.</Alert.Title>
				<Alert.Action>
					<Button variant="link" class="text-foreground">Повторить</Button>
				</Alert.Action>
			</Alert.Root>
			<Alert.Root role="status" class="border-l-grey-600">
				<Alert.Title>Ответила модель Pro: лимит Max на сегодня почти израсходован</Alert.Title>
			</Alert.Root>
			<Alert.Root role="status" class="border-l-grey-400">
				<Alert.Title>Т-Инвестиции подключены, найдено 2 счёта</Alert.Title>
			</Alert.Root>
			<Alert.Root role="status">
				<Alert.Title>2 числа в ответе не нашлись в данных</Alert.Title>
				<Alert.Action>
					<Button variant="link" class="text-foreground">Показать</Button>
				</Alert.Action>
			</Alert.Root>
		</div>
		<div class="flex flex-wrap gap-3">
			<Button
				variant="outline"
				onclick={() => toast.error('Т-Инвестиции не отвечают. Повторите позже.')}
				>Тост: ошибка</Button
			>
			<Button
				variant="outline"
				onclick={() => toast.success('Т-Инвестиции подключены, найдено 2 счёта')}
				>Тост: готово</Button
			>
			<Button variant="outline" onclick={() => toast('Ответ сохранён в чате')}>Тост: справка</Button
			>
		</div>
	</Demo>

	<Demo
		name="Данные"
		note="плюс цветом текста, минус красным, всегда со знаком; стрелка только у итога"
	>
		<div class="flex flex-wrap items-baseline gap-x-8 gap-y-3 tabular-nums">
			<span class="text-lead"
				><span aria-hidden="true">↑</span>&nbsp;{formatMoney('42090', 'RUB', {
					signed: true,
					digits: 0
				})}</span
			>
			<span class="text-[14px]"
				>{formatMoney('28050', 'RUB', { signed: true, digits: 0 })}
				<span class="text-[12px] text-muted-foreground"
					>{formatPercent('0.176', { signed: true, digits: 1 })}</span
				></span
			>
			<span class="text-[14px] text-negative"
				>{formatMoney('-23800', 'RUB', { signed: true, digits: 0 })}
				<span class="text-[12px]">{formatPercent('-0.147', { signed: true, digits: 1 })}</span
				></span
			>
			<span class="text-[12px] text-muted-foreground"
				>{formatMoney('34570', 'RUB', { signed: true, digits: 0 })} ({formatPercent('0.0426', {
					signed: true
				})})</span
			>
		</div>
	</Demo>

	<Demo name="Графика бренда" note="в приложении градиент значит «ИИ работает» или его действие">
		<div class="grid grid-cols-2 gap-4 text-caps md:grid-cols-4">
			{#each GRADIENTS as [utility, note] (utility)}
				<figure>
					<div class="h-16 {utility}" aria-hidden="true"></div>
					<figcaption class="mt-2">
						{utility}: <span class="text-muted-foreground">{note}</span>
					</figcaption>
				</figure>
			{/each}
			<figure>
				<div class="h-16 ki-halftone" aria-hidden="true"></div>
				<figcaption class="mt-2">
					ki-halftone: <span class="text-muted-foreground">полутон, шаг 4 px</span>
				</figcaption>
			</figure>
			<figure>
				<p class="h-16 font-serif text-body">
					<span class="ki-highlight px-1">Выручка выросла на 12 %</span>
				</p>
				<figcaption class="mt-2">
					ki-highlight: <span class="text-muted-foreground">подсветка ключевой фразы</span>
				</figcaption>
			</figure>
		</div>
	</Demo>

	<Demo name="Logo" note="«Kōri»: compact в шапке, spaced над формой входа, sign «Kō» в фавиконе">
		<div class="flex flex-wrap items-end gap-8">
			<Logo size="sm" />
			<Logo />
			<Logo size="lg" />
			<Logo variant="sign" size="sm" />
			<Logo variant="sign" />
			<Logo variant="sign" size="lg" />
		</div>
		<div class="flex flex-wrap items-end gap-12">
			<Logo variant="spaced" size="sm" />
			<Logo variant="spaced" size="md" />
		</div>
	</Demo>

	<Demo name="AppShell" note="сайдбар на десктопе, вкладки снизу на мобильном">
		<!-- transform keeps the fixed tab bar inside the frame -->
		<div class="h-[520px] [transform:translateZ(0)] overflow-hidden border">
			<AppShell nav={NAV} user={USER}>
				<PageHeader title="Портфель" description="Цены Т-Инвестиций на 10.10.2026, 19:00 МСК" />
			</AppShell>
		</div>
	</Demo>

	<Demo
		name="PageHeader"
		note="мета-строка 56 px: заголовок обычным регистром, пояснение, действия"
	>
		<div class="border">
			<PageHeader title="История" description="12 чатов">
				{#snippet actions()}
					<Button variant="secondary" size="sm"
						><span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат</Button
					>
				{/snippet}
			</PageHeader>
			<PageHeader title="Чат" />
		</div>
	</Demo>

	<Demo name="EmptyState">
		<EmptyState
			title="Чатов пока нет"
			description="Задайте вопрос о портфеле, и чат появится здесь."
		>
			{#snippet action()}
				<Button variant="secondary"
					><span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат</Button
				>
			{/snippet}
		</EmptyState>
	</Demo>

	<Demo name="ErrorState" note="рамка с полосой red-deep слева, код запроса с копированием">
		<ErrorState error={ERROR} onRetry={() => toast('Повторяю запрос')} />
	</Demo>

	<Demo name="LoadingBlock">
		<div class="grid gap-4 md:grid-cols-3">
			<LoadingBlock />
			<LoadingBlock variant="table" rows={4} />
			<LoadingBlock variant="chart" />
		</div>
	</Demo>

	<Demo name="DataTable" note="сортировка по клику на заголовок, клик по строке">
		<div class="grid gap-8 md:grid-cols-2">
			<DataTable
				columns={positions}
				rows={INSTRUMENTS}
				onRowClick={(row) => toast(`Выбран ${row.ticker}`)}
			/>
			<DataTable columns={positions} rows={[]} dense>
				{#snippet empty()}Инструментов нет{/snippet}
			</DataTable>
		</div>
	</Demo>

	<Demo name="ChartView" note="все девять видов ChartKind: структура плашками, остальное на холсте">
		<div class="grid gap-x-12 gap-y-10 md:grid-cols-2">
			{#each CHARTS as spec (spec.kind)}
				<ChartView {spec} height={260} />
			{/each}
		</div>
	</Demo>

	<Demo name="ArtifactTable">
		<ArtifactTable spec={TABLE} />
	</Demo>

	<Demo name="ArtifactImage">
		<div class="flex flex-wrap gap-4">
			{#each IMAGES as artifact (artifact.id)}
				<ArtifactImage {artifact} />
			{/each}
		</div>
	</Demo>

	<Demo name="ArtifactView" note="график, таблица и картинка через один компонент">
		<div class="space-y-8">
			{#each ARTIFACTS as artifact (artifact.id)}
				<ArtifactView {artifact} />
			{/each}
		</div>
	</Demo>

	<Demo
		name="Markdown"
		note="текст Noto Serif, числа моно, минус красным, маркеры обычные; HTML остаётся текстом"
	>
		<div class="max-w-[820px]">
			<Markdown source={MARKDOWN} sources={SOURCES} />
		</div>
	</Demo>

	<Demo name="SourceList" note="номер и строка через запятую, ссылка без стрелки">
		<div class="max-w-[820px]">
			<SourceList sources={SOURCES} />
		</div>
	</Demo>

	<Demo name="StatCard" note="без рамки, вертикальная линия между соседями">
		<div class="grid grid-cols-3">
			<StatCard
				label="Стоимость портфеля"
				value={formatMoney('1195145', 'RUB', { digits: 0 })}
				delta={{ text: '+3,2 % за месяц', trend: 'up' }}
				hint="все счета"
			/>
			<StatCard
				label="Доходность"
				value="−1,4 %"
				delta={{ text: '−0,6 % за неделю', trend: 'down' }}
			/>
			<StatCard label="Бета к IMOEX" value="0,92" loading />
		</div>
	</Demo>

	<Demo name="MoneyText">
		<div class="flex flex-wrap gap-6 text-ui">
			<MoneyText money={{ amount: '1185000.50', currency: 'RUB' }} />
			<MoneyText money={{ amount: '-31000', currency: 'RUB' }} signed colorize />
			<MoneyText money={{ amount: '12500', currency: 'RUB' }} signed colorize />
			<MoneyText money={{ amount: '2400000000', currency: 'RUB' }} compact />
			<MoneyText money={{ amount: '1520.35', currency: 'USD' }} />
		</div>
	</Demo>

	<Demo name="PercentText">
		<div class="flex flex-wrap gap-6 text-ui">
			<PercentText value="0.3217" />
			<PercentText value="0.0915" signed colorize />
			<PercentText value={-0.0561} signed colorize />
			<PercentText value="0.12345" digits={1} />
		</div>
	</Demo>

	<Demo
		name="InstrumentLogo"
		note="логотип или текст на нейтральной плитке: инициалы, «ОФЗ», код валюты"
	>
		<div class="flex flex-wrap items-center gap-4">
			{#each LOGO_SIZES as size (size)}
				<InstrumentLogo src={sber.logo_url} name={sber.name} {size} />
				<InstrumentLogo src={null} name="Газпром нефть" color={gazp.brand_color} {size} />
			{/each}
			<InstrumentLogo src={null} name="ОФЗ 26238" size={32} />
			<InstrumentLogo src={null} name="Доллар США" size={32} />
			<InstrumentLogo src={null} name="Т-Технологии" size={32} />
		</div>
	</Demo>

	<Demo name="InstrumentBadge">
		<div class="flex flex-wrap items-center gap-6">
			{#each INSTRUMENTS as instrument (instrument.uid)}
				<InstrumentBadge {instrument} />
			{/each}
			<InstrumentBadge instrument={gazp} size="md" />
		</div>
	</Demo>

	<Demo
		name="AccountSelect"
		note="до четырёх счетов вкладками, по имени; скрытый счёт не показывается"
	>
		<div class="flex flex-wrap items-center gap-4 text-ui">
			<AccountSelect accounts={ACCOUNTS} value={account} onChange={(alias) => (account = alias)} />
			<span class="text-muted-foreground">Выбрано: {chosen(account, ACCOUNTS)}</span>
		</div>
		<div class="flex flex-wrap items-center gap-4 text-ui">
			<AccountSelect accounts={MANY_ACCOUNTS} value={many} onChange={(alias) => (many = alias)} />
			<span class="text-muted-foreground"
				>Пять счетов списком, два одного имени: выбрано {chosen(many, MANY_ACCOUNTS)}</span
			>
		</div>
	</Demo>

	<Demo name="PeriodSelect">
		<div class="flex flex-wrap items-center gap-4 text-ui">
			<PeriodSelect value={period} onChange={(next) => (period = next)} />
		</div>
	</Demo>

	<Demo name="UsageMeter" note="полоса 6 px, красная засечка темпа; выше темпа заполнение светлеет">
		<div class="grid max-w-[640px] gap-3.5">
			<UsageMeter label="Lite" used={6_100_000} quota={250_000_000} pace={0.038} />
			<UsageMeter label="Pro" used={1_200_000} quota={40_000_000} pace={0.038} />
			<UsageMeter label="Max" used={2_400_000} quota={25_000_000} pace={0.038} />
			<UsageMeter label="Веб" used={38} quota={1000} unit="в октябре" />
		</div>
	</Demo>

	<Demo
		name="ConfirmDialog"
		note="белая панель, чёрная плашка заголовка без крестика, один × у действия «Удалить»"
	>
		<Button variant="outline" onclick={() => (confirming = true)}>Удалить чат</Button>
		<ConfirmDialog
			bind:open={confirming}
			title="Удалить чат?"
			description="«Что с моим портфелем и почему?» и 4 сообщения удалятся без возврата."
			confirmLabel="Удалить"
			destructive
			onConfirm={async () => {
				await pause(600);
				toast.success('Чат удалён');
			}}
		/>
	</Demo>

	<Demo name="CopyButton">
		<div class="flex items-center gap-2 text-ui">
			<code class="bg-muted px-1">SU26238RMFS4</code>
			<CopyButton text="SU26238RMFS4" label="Копировать тикер" />
		</div>
	</Demo>

	<Demo name="ThemeToggle" note="сегменты «Тёмная» и «Светлая», выбранный белый">
		<ThemeToggle />
	</Demo>

	<Demo name="Disclaimer" note="обычным регистром, под ответами с meta.disclaimer">
		<Disclaimer />
	</Demo>

	<Demo name="SSE" note="поток эха: dev.echo и run.finished через 200 мс">
		<div class="flex flex-wrap items-center gap-4">
			<Button variant="outline" onclick={sendEcho}>Эхо</Button>
			{#if echo}
				<p class="text-ui text-muted-foreground">
					статус {echo.view.status} · seq {echo.view.last_seq}
				</p>
			{/if}
		</div>
		{#if echoed}
			<pre aria-label="Ответ эха" class="text-ui break-all whitespace-pre-wrap">{echoed}</pre>
		{/if}
	</Demo>
</div>
