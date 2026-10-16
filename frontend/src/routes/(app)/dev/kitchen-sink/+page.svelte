<script lang="ts">
	import Bold from '@lucide/svelte/icons/bold';
	import Check from '@lucide/svelte/icons/check';
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
	import * as Tabs from '$lib/ui/tabs';
	import { Textarea } from '$lib/ui/textarea';
	import { Toggle } from '$lib/ui/toggle';
	import * as ToggleGroup from '$lib/ui/toggle-group';
	import * as Tooltip from '$lib/ui/tooltip';
	import { cn } from '$lib/utils/cn';
	import { formatMoney } from '$lib/utils/format';
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
		['ki-fade', 'красный → белый'],
		['ki-ignite', 'чёрный → красный'],
		['ki-ember', 'красный → бледно-красный'],
		['ki-hero', 'розовый → красный → чёрный'],
		['ki-tile', 'розовый → красный → серый']
	] as const;
	// The sheet «Выбранное» of v3: the menu, the model rows and the tabs of a phone.
	const MENU = ['Чат', 'История', 'Портфель', 'Настройки'];
	const MODELS = [
		['auto', 'Авто', 'подберёт модель по вопросу', 'Сейчас'],
		['lite', 'Lite', 'короткие ответы и сводки', 'Остаток 97 %'],
		['pro', 'Pro', 'анализ портфеля и бумаг', 'Остаток 97 %'],
		['max', 'Max', 'отчётность МСФО и РСБУ', 'Остаток 98 %']
	] as const;
	const [sber, gazp] = INSTRUMENTS as [InstrumentBrief, InstrumentBrief];
</script>

<PageHeader title="Kitchen sink" description="Примитивы §13.1 и компоненты §13.2 в текущей теме">
	{#snippet actions()}
		<ThemeToggle />
	{/snippet}
</PageHeader>

<div class="space-y-14 p-4 md:p-12">
	<section aria-label="Примитивы" class="space-y-4">
		<h2 class="border-b pb-3 text-caption uppercase">Примитивы shadcn-svelte</h2>
		<div class="grid gap-8 md:grid-cols-2">
			<div class="flex flex-wrap items-center gap-2">
				<Badge>Подключён</Badge>
				<Badge variant="secondary">облигация</Badge>
				<Badge variant="outline">acc1</Badge>
				<Badge variant="destructive">ошибка</Badge>
				<Toggle aria-label="Жирный"><Bold /></Toggle>
			</div>
			<div class="space-y-3">
				<Label for="ks-token">Токен Т-Инвестиций</Label>
				<Input id="ks-token" type="password" placeholder="t.только-чтение" />
				<Label for="ks-question">Вопрос</Label>
				<Textarea id="ks-question" placeholder="Что с моим портфелем?" />
			</div>
			<div class="space-y-3">
				<div class="flex items-center gap-3">
					<Checkbox id="ks-agree" bind:checked={agree} />
					<Label for="ks-agree">Токен только для чтения</Label>
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
					<Button variant="outline" onclick={() => toast.success('Сохранено')}>Тост</Button>
				</div>
			</div>
			<div class="space-y-3">
				<Collapsible.Root class="space-y-2">
					<Collapsible.Trigger class={buttonVariants({ variant: 'ghost', size: 'sm' })}>
						Шаги рана <span aria-hidden="true">↓</span>
					</Collapsible.Trigger>
					<Collapsible.Content class="text-ui text-muted-foreground">
						Загружаю портфель → строю таблицу
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

	<Demo name="Кнопки" note="ячейка-глиф и подпись цветом текста; сплошной красной заливки нет">
		<div class="flex flex-wrap items-center gap-x-5 gap-y-4">
			<Button size="lg"><span data-slot="button-glyph" aria-hidden="true">→</span>Войти</Button>
			<Button variant="secondary" size="lg"
				><span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат</Button
			>
			<Button variant="ai" size="lg"
				><span data-slot="button-glyph" aria-hidden="true">→</span>Спросить</Button
			>
			<Button variant="ai" size="icon" aria-label="Отправить вопрос">
				<span aria-hidden="true">→</span>
			</Button>
			<Button variant="outline" size="lg">Подключить токен</Button>
			<Button variant="destructive" size="lg"
				><span data-slot="button-glyph" aria-hidden="true">→</span>Отключить</Button
			>
			<Button variant="link">Подробнее</Button>
			<Button variant="ghost">Призрак</Button>
		</div>
		<div class="flex flex-wrap items-center gap-x-5 gap-y-4">
			<Button><span data-slot="button-glyph" aria-hidden="true">→</span>40 px</Button>
			<Button size="lg"><span data-slot="button-glyph" aria-hidden="true">→</span>48 px</Button>
			<Button disabled><span data-slot="button-glyph" aria-hidden="true">→</span>Недоступно</Button>
			<Button variant="secondary" disabled
				><span data-slot="button-glyph" aria-hidden="true">+</span>Недоступно</Button
			>
			<Button variant="link" disabled>Недоступно</Button>
		</div>
		<!-- On a white panel the ink label turns black (tech.md §13.1). -->
		<div class="theme-day flex flex-wrap bg-background">
			<Button variant="secondary" size="lg" class="min-w-44 flex-1 justify-start"
				><span data-slot="button-glyph" aria-hidden="true">×</span>Отмена</Button
			>
			<Button size="lg" class="min-w-44 flex-1 justify-start"
				><span data-slot="button-glyph" aria-hidden="true">→</span>Войти</Button
			>
			<Button variant="destructive" size="lg" class="min-w-44 flex-1 justify-start"
				><span data-slot="button-glyph" aria-hidden="true">→</span>Удалить</Button
			>
		</div>
	</Demo>

	<Demo
		name="Выбранное"
		note="выбранное белое: стрелка и тёмная строка в меню, инверсия в остальном"
	>
		<div class="grid gap-10 lg:grid-cols-2">
			<ul aria-label="Меню" class="w-60 border-y text-caps uppercase">
				{#each MENU as item, i (item)}
					<li
						class={cn(
							'flex h-9 items-center gap-2 px-5',
							i === 2 ? 'bg-accent text-foreground' : 'text-muted-foreground'
						)}
					>
						<span
							aria-hidden="true"
							class={cn('w-3.5 text-ui text-primary', i === 2 && "before:content-['→']")}
						></span>{item}
					</li>
				{/each}
			</ul>
			<div class="space-y-5">
				<Tabs.Root value="active">
					<Tabs.List>
						<Tabs.Trigger value="active">Активные</Tabs.Trigger>
						<Tabs.Trigger value="archive">Архив</Tabs.Trigger>
					</Tabs.List>
					<Tabs.Content value="active" class="text-ui">Треды за неделю.</Tabs.Content>
					<Tabs.Content value="archive" class="text-ui">Архивные треды.</Tabs.Content>
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
						class="flex h-13 cursor-pointer items-center gap-4 border-b border-line-faint px-4 text-ui normal-case last:border-0 hover:bg-accent has-data-checked:bg-foreground has-data-checked:text-background"
					>
						<RadioGroup.Item {value} />
						<span class="w-12">{label}</span>
						<span class="flex-1 opacity-70">{note}</span>
						<span class="text-caption uppercase">{left}</span>
					</Label>
				{/each}
			</RadioGroup.Root>
			<!-- The tabs of a phone: the chosen one white under a red line. -->
			<ul aria-label="Вкладки телефона" class="grid h-16 max-w-[390px] grid-cols-4 border">
				{#each NAV as item (item.id)}
					<li
						class={cn(
							'relative flex flex-col items-center justify-center gap-1.5 text-[10px]/3 tracking-[0.08em] uppercase',
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
						<h3 id="ks-broker" class="text-caps uppercase">Брокер</h3>
						<p class="text-[13px]/5 text-muted-foreground">
							Т-Инвестиции, токен с доступом только на чтение
						</p>
					</div>
					<Badge>Подключён</Badge>
				</header>
				<dl
					class="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-x-6 gap-y-4 border-b border-line-faint px-6 py-5"
				>
					{#each [['Токен', 't.••••only'], ['Доступ', 'Только чтение'], ['Проверен', '10.10.2026 09:00']] as [term, detail] (term)}
						<div>
							<dt class="text-caption text-grey-600 uppercase">{term}</dt>
							<dd class="mt-1.5 text-[15px]/5">{detail}</dd>
						</div>
					{/each}
				</dl>
				<footer class="flex flex-wrap justify-end gap-3 px-6 py-4">
					<Button variant="outline">Проверить токен</Button>
					<Button variant="destructive"
						><span data-slot="button-glyph" aria-hidden="true">→</span>Отключить</Button
					>
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
					delta={{ text: '+3,65 % от покупки', trend: 'up' }}
				/>
				<StatCard label="Позиции" value="10" hint="на 2 счетах" />
			</div>
		</div>
	</Demo>

	<Demo
		name="Уведомления"
		note="ячейка-знак слева: × ошибка, ↓ понижение, галочка готово, → справка"
	>
		<div class="grid max-w-[640px] gap-2">
			<Alert.Root variant="destructive">
				<span data-slot="alert-glyph" aria-hidden="true">×</span>
				<Alert.Title>
					Т-Инвестиции недоступны, попробуйте позже
					<span class="ml-2 text-caption text-grey-600">req-7f3a2c</span>
				</Alert.Title>
				<Alert.Action>
					<Button variant="link" class="text-caption text-foreground">Повторить</Button>
				</Alert.Action>
			</Alert.Root>
			<Alert.Root role="status">
				<span data-slot="alert-glyph" aria-hidden="true" class="bg-grey-600 text-white">↓</span>
				<Alert.Title>Модель понижена до Pro: Max идёт выше темпа расхода</Alert.Title>
			</Alert.Root>
			<Alert.Root role="status">
				<span data-slot="alert-glyph" aria-hidden="true" class="bg-grey-400 text-black"
					><Check /></span
				>
				<Alert.Title>Токен подключён, найдено 2 счёта</Alert.Title>
			</Alert.Root>
			<Alert.Root role="status">
				<span data-slot="alert-glyph" aria-hidden="true">→</span>
				<Alert.Title>2 числа в ответе не подтверждены инструментами</Alert.Title>
				<Alert.Action>
					<Button variant="link" class="text-caption text-foreground">Показать</Button>
				</Alert.Action>
			</Alert.Root>
		</div>
	</Demo>

	<Demo name="Графика бренда" note="градиент значит «ИИ работает» или его действие">
		<div class="grid grid-cols-2 gap-4 text-caption md:grid-cols-4">
			{#each GRADIENTS as [utility, note] (utility)}
				<figure>
					<div class="h-16 {utility}" aria-hidden="true"></div>
					<figcaption class="mt-2">
						{utility} · <span class="text-muted-foreground">{note}</span>
					</figcaption>
				</figure>
			{/each}
			<figure>
				<div class="h-16 ki-halftone" aria-hidden="true"></div>
				<figcaption class="mt-2">
					ki-halftone · <span class="text-muted-foreground">полутон, шаг 4 px</span>
				</figcaption>
			</figure>
			<figure>
				<p class="h-16 text-body"><span class="ki-highlight px-1">Выручка выросла на 12 %</span></p>
				<figcaption class="mt-2">
					ki-highlight · <span class="text-muted-foreground">подсветка фразы</span>
				</figcaption>
			</figure>
		</div>
	</Demo>

	<Demo
		name="Logo"
		note="печать 氷: compact в шапке, spaced на обложке, sign у ответа и в фавиконе"
	>
		<div class="flex flex-wrap items-end gap-8">
			<Logo size="sm" />
			<Logo />
			<Logo size="lg" />
			<Logo variant="sign" size="sm" />
			<Logo variant="sign" />
			<Logo variant="sign" size="lg" />
		</div>
		<Logo variant="spaced" />
	</Demo>

	<Demo name="AppShell" note="сайдбар на десктопе, вкладки снизу на мобильном">
		<!-- transform keeps the fixed tab bar inside the frame -->
		<div class="h-[520px] [transform:translateZ(0)] overflow-hidden border">
			<AppShell nav={NAV} user={USER}>
				<PageHeader title="Портфель" description="Содержимое вкладки" />
			</AppShell>
		</div>
	</Demo>

	<Demo name="PageHeader" note="мета-строка 56 px">
		<div class="border">
			<PageHeader title="История" description="Треды и поиск по ним">
				{#snippet actions()}
					<Button variant="secondary" size="sm"
						><span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат</Button
					>
				{/snippet}
			</PageHeader>
			<PageHeader title="Чат" description="Без действий справа остаётся кана" />
		</div>
	</Demo>

	<Demo name="EmptyState">
		<EmptyState
			title="Пока нет тредов"
			description="Задайте вопрос о портфеле, и тред появится здесь."
		>
			{#snippet action()}
				<Button><span data-slot="button-glyph" aria-hidden="true">+</span>Новый чат</Button>
			{/snippet}
		</EmptyState>
	</Demo>

	<Demo name="ErrorState">
		<ErrorState error={ERROR} onRetry={() => toast.info('Повторяю запрос')} />
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
		note="текст серым, числа цветом текста, минус красным; HTML остаётся текстом"
	>
		<div class="max-w-[820px]">
			<Markdown source={MARKDOWN} sources={SOURCES} />
		</div>
	</Demo>

	<Demo name="SourceList">
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
				hint="Все счета"
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

	<Demo name="InstrumentLogo" note="логотип или инициалы на нейтральной плитке">
		<div class="flex flex-wrap items-center gap-4">
			{#each LOGO_SIZES as size (size)}
				<InstrumentLogo src={sber.logo_url} name={sber.name} {size} />
				<InstrumentLogo src={null} name="Газпром нефть" color={gazp.brand_color} {size} />
			{/each}
			<InstrumentLogo src={null} name="ОФЗ 26238" />
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

	<Demo name="AccountSelect" note="до четырёх счетов вкладками; скрытый счёт не показывается">
		<div class="flex flex-wrap items-center gap-4 text-ui">
			<AccountSelect accounts={ACCOUNTS} value={account} onChange={(alias) => (account = alias)} />
			<span class="text-muted-foreground">Выбрано: {account ?? 'все счета'}</span>
		</div>
		<div class="flex flex-wrap items-center gap-4 text-ui">
			<AccountSelect accounts={MANY_ACCOUNTS} value={many} onChange={(alias) => (many = alias)} />
			<span class="text-muted-foreground">Пять счетов: список, выбрано {many ?? 'все счета'}</span>
		</div>
	</Demo>

	<Demo name="PeriodSelect">
		<div class="flex flex-wrap items-center gap-4 text-ui">
			<PeriodSelect value={period} onChange={(next) => (period = next)} />
			<span class="text-muted-foreground">Период: {period}</span>
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

	<Demo name="ConfirmDialog" note="белая панель, чёрная плашка заголовка, две кнопки">
		<Button variant="destructive" onclick={() => (confirming = true)}
			><span data-slot="button-glyph" aria-hidden="true">→</span>Удалить тред</Button
		>
		<ConfirmDialog
			bind:open={confirming}
			title="Удалить тред?"
			description="«Что с моим портфелем и почему?» и 4 сообщения удалятся без возврата."
			confirmLabel="Удалить"
			destructive
			onConfirm={async () => {
				await pause(600);
				toast.success('Тред удалён');
			}}
		/>
	</Demo>

	<Demo name="CopyButton">
		<div class="flex items-center gap-2 text-ui">
			<code class="bg-muted px-1">SU26238RMFS4</code>
			<CopyButton text="SU26238RMFS4" label="Копировать тикер" />
		</div>
	</Demo>

	<Demo name="ThemeToggle" note="сегменты «Ночь» и «День», выбранный белый">
		<ThemeToggle />
	</Demo>

	<Demo name="Disclaimer">
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
