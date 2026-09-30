<script lang="ts">
	import Bold from '@lucide/svelte/icons/bold';
	import Inbox from '@lucide/svelte/icons/inbox';
	import type { ColumnDef } from '@tanstack/table-core';
	import { toast } from 'svelte-sonner';
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
	import type { InstrumentBrief, PeriodCode } from '$lib/types';
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
	import * as Tooltip from '$lib/ui/tooltip';
	import { formatMoney } from '$lib/utils/format';
	import Demo from './components/Demo.svelte';
	import {
		ACCOUNTS,
		ARTIFACTS,
		CHARTS,
		ERROR,
		IMAGES,
		INSTRUMENTS,
		MARKDOWN,
		SOURCES,
		TABLE,
		USER
	} from './fixtures';

	let account = $state<string | null>(null);
	let period = $state<PeriodCode>('1y');
	let confirming = $state(false);
	let notify = $state(true);
	let agree = $state(false);

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
	const [sber, gazp] = INSTRUMENTS as [InstrumentBrief, InstrumentBrief];
</script>

<div class="mx-auto max-w-[1200px] space-y-8 px-4 py-6 md:px-8">
	<PageHeader
		title="Kitchen sink"
		description="Примитивы §13.1 и компоненты §13.2 в текущей теме; тема переключается справа"
	>
		{#snippet actions()}
			<ThemeToggle />
		{/snippet}
	</PageHeader>

	<section aria-label="Примитивы" class="space-y-4">
		<h2 class="text-xs tracking-wider text-muted-foreground uppercase">Примитивы shadcn-svelte</h2>
		<div class="grid gap-6 md:grid-cols-2">
			<div class="flex flex-wrap items-center gap-2">
				<Button>Главное <span aria-hidden="true">→</span></Button>
				<Button variant="secondary">Второе</Button>
				<Button variant="outline">Рамка <span aria-hidden="true">→</span></Button>
				<Button variant="ghost">Призрак</Button>
				<Button variant="destructive">Удалить</Button>
				<Button variant="link"><span aria-hidden="true">→</span> Ссылка</Button>
				<Button disabled>Недоступно</Button>
			</div>
			<div class="flex flex-wrap items-center gap-2 md:col-span-2">
				<Button variant="secondary"
					><span data-slot="button-glyph" aria-hidden="true">+</span>Добавить счёт</Button
				>
				<Button variant="ai"
					><span data-slot="button-glyph" aria-hidden="true">→</span>Разобрать подробно</Button
				>
				<Button><span data-slot="button-glyph" aria-hidden="true">→</span>Подключить токен</Button>
				<Button variant="secondary" disabled
					><span data-slot="button-glyph" aria-hidden="true">+</span>Недоступно</Button
				>
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<Badge>новое</Badge>
				<Badge variant="secondary">облигация</Badge>
				<Badge variant="outline">acc1</Badge>
				<Badge variant="destructive">ошибка</Badge>
				<Toggle aria-label="Жирный"><Bold /></Toggle>
			</div>
			<div class="space-y-2">
				<Label for="ks-token">Токен T-Invest</Label>
				<Input id="ks-token" type="password" placeholder="t.xxxxxxxx" />
				<Label for="ks-question">Вопрос</Label>
				<Textarea id="ks-question" placeholder="Что с моим портфелем?" />
			</div>
			<div class="space-y-3">
				<div class="flex items-center gap-2">
					<Switch id="ks-notify" bind:checked={notify} />
					<Label for="ks-notify">Уведомления</Label>
				</div>
				<div class="flex items-center gap-2">
					<Checkbox id="ks-agree" bind:checked={agree} />
					<Label for="ks-agree">Токен только для чтения</Label>
				</div>
				<RadioGroup.Root value="concise" aria-label="Стиль ответа">
					<div class="flex items-center gap-2">
						<RadioGroup.Item value="concise" id="ks-concise" />
						<Label for="ks-concise">Кратко</Label>
					</div>
					<div class="flex items-center gap-2">
						<RadioGroup.Item value="detailed" id="ks-detailed" />
						<Label for="ks-detailed">Подробно</Label>
					</div>
				</RadioGroup.Root>
			</div>
			<Card.Root>
				<Card.Header>
					<Card.Title>Карточка</Card.Title>
					<Card.Description>Подпись карточки</Card.Description>
				</Card.Header>
				<Card.Content>Содержимое карточки.</Card.Content>
			</Card.Root>
			<Alert.Root>
				<Alert.Title>Брокер не подключён</Alert.Title>
				<Alert.Description>Добавьте токен в Настройках.</Alert.Description>
			</Alert.Root>
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
					<Popover.Trigger class={buttonVariants({ variant: 'outline' })}>Поповер</Popover.Trigger>
					<Popover.Content>Подсказка с содержимым.</Popover.Content>
				</Popover.Root>
				<Tooltip.Provider>
					<Tooltip.Root>
						<Tooltip.Trigger class={buttonVariants({ variant: 'outline' })}>Тултип</Tooltip.Trigger>
						<Tooltip.Content>Короткая подсказка</Tooltip.Content>
					</Tooltip.Root>
				</Tooltip.Provider>
				<Button variant="outline" onclick={() => toast.success('Сохранено')}>Тост</Button>
			</div>
			<Tabs.Root value="active">
				<Tabs.List>
					<Tabs.Trigger value="active">Активные</Tabs.Trigger>
					<Tabs.Trigger value="archive">Архив</Tabs.Trigger>
				</Tabs.List>
				<Tabs.Content value="active" class="text-xs">Треды за неделю.</Tabs.Content>
				<Tabs.Content value="archive" class="text-xs">Архивные треды.</Tabs.Content>
			</Tabs.Root>
			<Collapsible.Root class="space-y-2">
				<Collapsible.Trigger class={buttonVariants({ variant: 'ghost', size: 'sm' })}>
					Шаги рана
				</Collapsible.Trigger>
				<Collapsible.Content class="text-xs text-muted-foreground">
					Загружаю портфель → строю таблицу
				</Collapsible.Content>
			</Collapsible.Root>
			<ScrollArea class="h-24 border p-2 text-xs">
				{#each { length: 12 }, i (i)}
					<p>Строка {i + 1}</p>
				{/each}
			</ScrollArea>
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

	<section aria-label="Графика бренда" class="space-y-3 border-t pt-4">
		<h2 class="text-xs tracking-wider text-muted-foreground uppercase">Графика бренда</h2>
		<div class="grid grid-cols-2 gap-4 text-xs md:grid-cols-4">
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
				<p class="h-16 text-sm"><span class="ki-highlight px-1">Выручка выросла на 12 %</span></p>
				<figcaption class="mt-2">
					ki-highlight · <span class="text-muted-foreground">подсветка фразы</span>
				</figcaption>
			</figure>
			<figure class="w-fit bg-grey-200 p-2">
				<div class="h-16 w-32 ki-tile" aria-hidden="true"></div>
				<figcaption class="pt-2 text-center text-2xl leading-none text-black">Kō</figcaption>
			</figure>
		</div>
	</section>

	<Demo name="Logo" note="compact в шапке, spaced на обложке, sign на плитке и в фавиконе">
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
		<div class="h-[420px] [transform:translateZ(0)] overflow-hidden border">
			<AppShell nav={NAV} user={USER}>
				<PageHeader title="Портфель" description="Содержимое вкладки" />
			</AppShell>
		</div>
	</Demo>

	<Demo name="PageHeader">
		<PageHeader title="История" description="Треды и поиск по ним">
			{#snippet actions()}
				<Button size="sm">Новый чат</Button>
			{/snippet}
		</PageHeader>
	</Demo>

	<Demo name="EmptyState">
		<EmptyState
			icon={Inbox}
			title="Пока нет тредов"
			description="Задайте вопрос о портфеле, и тред появится здесь."
		>
			{#snippet action()}
				<Button size="sm">Новый чат</Button>
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
		<div class="grid gap-4 md:grid-cols-2">
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

	<Demo name="ChartView" note="все девять видов ChartKind">
		<div class="grid gap-4 md:grid-cols-2">
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
		<div class="space-y-4">
			{#each ARTIFACTS as artifact (artifact.id)}
				<ArtifactView {artifact} />
			{/each}
		</div>
	</Demo>

	<Demo name="Markdown" note="сырой HTML и картинки из текста остаются текстом">
		<div class="max-w-[820px]">
			<Markdown source={MARKDOWN} sources={SOURCES} />
		</div>
	</Demo>

	<Demo name="SourceList">
		<SourceList sources={SOURCES} />
	</Demo>

	<Demo name="StatCard">
		<div class="grid gap-4 md:grid-cols-3">
			<StatCard
				label="Стоимость портфеля"
				value={formatMoney('1185000', 'RUB')}
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
		<div class="flex flex-wrap gap-6 text-sm">
			<MoneyText money={{ amount: '1185000.50', currency: 'RUB' }} />
			<MoneyText money={{ amount: '-31000', currency: 'RUB' }} signed colorize />
			<MoneyText money={{ amount: '12500', currency: 'RUB' }} signed colorize />
			<MoneyText money={{ amount: '2400000000', currency: 'RUB' }} compact />
			<MoneyText money={{ amount: '1520.35', currency: 'USD' }} />
		</div>
	</Demo>

	<Demo name="PercentText">
		<div class="flex flex-wrap gap-6 text-sm">
			<PercentText value="0.3217" />
			<PercentText value="0.0915" signed colorize />
			<PercentText value={-0.0561} signed colorize />
			<PercentText value="0.12345" digits={1} />
		</div>
	</Demo>

	<Demo name="InstrumentLogo" note="логотип или инициалы на цвете бренда">
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

	<Demo name="AccountSelect" note="скрытый счёт не показывается">
		<div class="flex items-center gap-3 text-xs">
			<AccountSelect accounts={ACCOUNTS} value={account} onChange={(alias) => (account = alias)} />
			<span class="text-muted-foreground">Выбрано: {account ?? 'все счета'}</span>
		</div>
	</Demo>

	<Demo name="PeriodSelect">
		<div class="flex flex-wrap items-center gap-3 text-xs">
			<PeriodSelect value={period} onChange={(next) => (period = next)} />
			<span class="text-muted-foreground">Период: {period}</span>
		</div>
	</Demo>

	<Demo name="UsageMeter" note="отметка темпа; выше темпа шкала желтеет">
		<div class="grid max-w-xl gap-4">
			<UsageMeter
				label="GigaChat Lite"
				used={41_200_000}
				quota={250_000_000}
				pace={0.18}
				unit="ток."
			/>
			<UsageMeter
				label="GigaChat Pro"
				used={9_800_000}
				quota={40_000_000}
				pace={0.18}
				unit="ток."
			/>
			<UsageMeter label="Tavily" used={212} quota={1000} unit="кр." />
		</div>
	</Demo>

	<Demo name="ConfirmDialog">
		<Button variant="destructive" onclick={() => (confirming = true)}>Удалить тред</Button>
		<ConfirmDialog
			bind:open={confirming}
			title="Удалить тред?"
			description="Сообщения и ответы исчезнут без возврата."
			confirmLabel="Удалить"
			destructive
			onConfirm={async () => {
				await pause(600);
				toast.success('Тред удалён');
			}}
		/>
	</Demo>

	<Demo name="CopyButton">
		<div class="flex items-center gap-2 text-xs">
			<code class="bg-muted px-1">SU26238RMFS4</code>
			<CopyButton text="SU26238RMFS4" label="Копировать тикер" />
		</div>
	</Demo>

	<Demo name="ThemeToggle">
		<ThemeToggle />
	</Demo>

	<Demo name="Disclaimer">
		<Disclaimer />
	</Demo>
</div>
