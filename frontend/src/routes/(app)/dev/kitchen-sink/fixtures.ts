// Demo data of the kitchen-sink: artifacts and API models as the backend sends them.
import type {
	ApiError,
	ArtifactOut,
	BrokerAccountOut,
	ChartSpec,
	InstrumentBrief,
	SourceRef,
	TableSpec,
	UserOut
} from '$lib/types';

type Axis = ChartSpec['x'];
type Series = ChartSpec['series'][number];
type Point = Series['points'][number];

function axis(type: Axis['type'], format: Axis['format'] = null, unit: string | null = null): Axis {
	return { type, label: null, format, unit };
}

function point(fields: Partial<Point>): Point {
	return { x: '', y: null, o: null, h: null, l: null, c: null, y_cat: null, z: null, ...fields };
}

function series(name: string, points: Point[], role: Series['role'] = null): Series {
	return { name, points, axis: 'y', role };
}

function chart(
	kind: ChartSpec['kind'],
	title: string,
	x: Axis,
	y: Axis,
	list: Series[],
	subtitle: string | null = null
): ChartSpec {
	return { kind, title, subtitle, x, y, y2: null, series: list, source_ids: [] };
}

/** Weekdays from 4 May 2026: a stable stand-in for trading days. */
const DAYS = (() => {
	const days: string[] = [];
	const day = new Date('2026-05-04T00:00:00Z');
	while (days.length < 90) {
		if (day.getUTCDay() % 6 !== 0) days.push(day.toISOString().slice(0, 10));
		day.setUTCDate(day.getUTCDate() + 1);
	}
	return days;
})();

/** A smooth made-up series: a drift with two waves on top. */
const wave = (i: number, base: number, swing: number, drift: number) =>
	base + drift * i + swing * Math.sin(i / 6) + (swing / 3) * Math.sin(i / 2.3);
const kopecks = (value: number) => Math.round(value * 100) / 100;

const candles = DAYS.slice(-30).map((day, i) => {
	const o = kopecks(wave(i, 300, 6, 0.2));
	const c = kopecks(wave(i + 1, 300, 6, 0.2));
	return point({ x: day, o, c, h: Math.max(o, c) + 1.8, l: Math.min(o, c) - 1.6 });
});

const TICKERS = ['SBER', 'GAZP', 'LKOH', 'YDEX'];
const CORRELATION = [
	[1, 0.62, 0.48, 0.21],
	[0.62, 1, 0.55, -0.12],
	[0.48, 0.55, 1, 0.08],
	[0.21, -0.12, 0.08, 1]
];

/** One chart of each kind (S1-06 AC 2). */
export const CHARTS: ChartSpec[] = [
	chart('line', 'Стоимость портфеля', axis('time', 'date'), axis('value', 'money', 'RUB'), [
		series(
			'Портфель',
			DAYS.map((day, i) => point({ x: day, y: kopecks(wave(i, 1_180_000, 25_000, 800)) }))
		)
	]),
	chart(
		'area',
		'Доходность портфеля и индекса',
		axis('time', 'date'),
		axis('value', 'percent'),
		[
			series(
				'Портфель',
				DAYS.map((day, i) => point({ x: day, y: wave(i, 0, 0.02, 0.0009) })),
				'primary'
			),
			series(
				'IMOEX',
				DAYS.map((day, i) => point({ x: day, y: wave(i, 0, 0.015, 0.0005) })),
				'benchmark'
			)
		],
		'С 4 мая 2026'
	),
	chart(
		'bar',
		'Дивиденды и купоны по месяцам',
		axis('category', 'month'),
		axis('value', 'money', 'RUB'),
		[
			series(
				'Выплаты',
				[4_200, 0, 12_800, 3_100, 27_400, 6_900].map((y, i) => point({ x: `2026-0${i + 4}-01`, y }))
			)
		]
	),
	chart('stacked_bar', 'Выручка по сегментам', axis('category'), axis('value', 'compact'), [
		series(
			'Розница',
			[2.1e12, 2.4e12, 2.8e12, 3.1e12, 3.3e12].map((y, i) => point({ x: `${2021 + i}`, y }))
		),
		series(
			'Корпоративный',
			[1.4e12, 1.5e12, 1.9e12, 2.2e12, 2.4e12].map((y, i) => point({ x: `${2021 + i}`, y }))
		),
		series(
			'Инвестиции',
			[0.3e12, 0.35e12, 0.5e12, 0.6e12, 0.7e12].map((y, i) => point({ x: `${2021 + i}`, y }))
		)
	]),
	chart('pie', 'Структура портфеля', axis('category'), axis('value', 'money', 'RUB'), [
		series('Типы', [
			point({ x: 'Акции', y: 612_000 }),
			point({ x: 'Облигации', y: 318_000 }),
			point({ x: 'Фонды', y: 184_000 }),
			point({ x: 'Валюта', y: 71_000 })
		])
	]),
	chart(
		'candlestick',
		'SBER, дневные свечи',
		axis('category', 'date'),
		axis('value', 'money', 'RUB'),
		[series('SBER', candles)]
	),
	chart('scatter', 'Риск и доходность за год', axis('value', 'percent'), axis('value', 'percent'), [
		series('Акции', [
			point({ x: 0.28, y: 0.14 }),
			point({ x: 0.31, y: 0.05 }),
			point({ x: 0.24, y: 0.19 }),
			point({ x: 0.36, y: -0.04 })
		]),
		series('Облигации', [
			point({ x: 0.06, y: 0.11 }),
			point({ x: 0.09, y: 0.13 }),
			point({ x: 0.04, y: 0.09 })
		])
	]),
	chart('heatmap', 'Корреляция доходностей', axis('category'), axis('category'), [
		series(
			'Корреляция',
			TICKERS.flatMap((row, i) =>
				TICKERS.map((column, j) => point({ x: column, y_cat: row, z: CORRELATION[i]?.[j] ?? 0 }))
			)
		)
	]),
	chart(
		'waterfall',
		'Изменение стоимости за сентябрь',
		axis('category'),
		axis('value', 'money', 'RUB'),
		[
			series('Изменение', [
				point({ x: 'Пополнения', y: 50_000 }),
				point({ x: 'Дивиденды', y: 12_500 }),
				point({ x: 'Купоны', y: 4_300 }),
				point({ x: 'Переоценка', y: -31_000 }),
				point({ x: 'Комиссии', y: -1_200 }),
				point({ x: 'Налоги', y: -1_600 })
			])
		]
	)
];

const svg = (body: string) =>
	`data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">${body}</svg>`)}`;

export const INSTRUMENTS: InstrumentBrief[] = [
	{
		uid: '0c7bf8e0-7d0e-4a38-9b57-2a1f3c6c1a01',
		ticker: 'SBER',
		class_code: 'TQBR',
		name: 'Сбербанк',
		instrument_type: 'share',
		currency: 'RUB',
		logo_url: svg(
			'<rect width="40" height="40" fill="#21a038"/><circle cx="20" cy="20" r="10" fill="none" stroke="#fff" stroke-width="4"/>'
		),
		brand_color: '#21a038'
	},
	{
		uid: '0c7bf8e0-7d0e-4a38-9b57-2a1f3c6c1a02',
		ticker: 'GAZP',
		class_code: 'TQBR',
		name: 'Газпром',
		instrument_type: 'share',
		currency: 'RUB',
		logo_url: null,
		brand_color: '#1b6fb7'
	},
	{
		uid: '0c7bf8e0-7d0e-4a38-9b57-2a1f3c6c1a03',
		ticker: 'LKOH',
		class_code: 'TQBR',
		name: 'Лукойл',
		instrument_type: 'share',
		currency: 'RUB',
		logo_url: null,
		brand_color: '#e8b923'
	},
	{
		uid: '0c7bf8e0-7d0e-4a38-9b57-2a1f3c6c1a04',
		ticker: 'SU26238RMFS4',
		class_code: 'TQOB',
		name: 'ОФЗ 26238',
		instrument_type: 'bond',
		currency: 'RUB',
		logo_url: null,
		brand_color: null
	}
];

const [sber, gazp, lkoh, ofz] = INSTRUMENTS as [
	InstrumentBrief,
	InstrumentBrief,
	InstrumentBrief,
	InstrumentBrief
];

export const TABLE: TableSpec = {
	title: 'Крупнейшие позиции',
	columns: [
		{ key: 'instrument', label: 'Инструмент', type: 'instrument', currency: null, digits: null },
		{ key: 'quantity', label: 'Количество', type: 'number', currency: null, digits: 0 },
		{ key: 'value', label: 'Стоимость', type: 'money', currency: 'RUB', digits: null },
		{ key: 'weight', label: 'Доля', type: 'percent', currency: null, digits: 1 },
		{ key: 'yield', label: 'Доходность', type: 'percent', currency: null, digits: 2 },
		{ key: 'bought', label: 'Покупка', type: 'date', currency: null, digits: null }
	],
	rows: [
		{
			instrument: sber.uid,
			quantity: '1200',
			value: '381240.00',
			weight: '0.3217',
			yield: '0.1432',
			bought: '2025-03-14'
		},
		{
			instrument: gazp.uid,
			quantity: '1500',
			value: '214650.00',
			weight: '0.1811',
			yield: '-0.0561',
			bought: '2025-06-02'
		},
		{
			instrument: lkoh.uid,
			quantity: '30',
			value: '208350.00',
			weight: '0.1758',
			yield: '0.0915',
			bought: '2024-11-20'
		},
		{
			instrument: ofz.uid,
			quantity: '350',
			value: '318010.50',
			weight: '0.2683',
			yield: null,
			bought: null
		}
	],
	total: { instrument: 'Итого', value: '1122250.50', weight: '0.9469' },
	note: 'Цены на 30.09.2026, 19:00 МСК.',
	instruments: Object.fromEntries(INSTRUMENTS.map((instrument) => [instrument.uid, instrument])),
	source_ids: []
};

function artifact(
	localId: string,
	kind: ArtifactOut['kind'],
	spec: ArtifactOut['spec'],
	imageUrl: string | null = null
): ArtifactOut {
	return {
		// A stable uuid per local id: its characters in hex fill the last group.
		id: `4f1d7a52-9c1e-4c8b-8f2e-${[...localId]
			.map((c) => c.charCodeAt(0).toString(16))
			.join('')
			.padStart(12, '0')}`,
		local_id: localId,
		kind,
		spec,
		image_url: imageUrl,
		created_at: '2026-09-30T16:00:00Z'
	};
}

const PICTURE = svg(
	'<rect width="40" height="40" fill="#f6f6f6"/><path d="M4 32 L14 20 L22 26 L36 8" fill="none" stroke="#fe2627" stroke-width="2"/>'
);

export const IMAGES: ArtifactOut[] = [
	artifact(
		'i1',
		'image',
		{
			source: 'web',
			logo_base: null,
			url: 'https://example.com/chart.png',
			document_id: null,
			page: null,
			alt: 'Динамика индекса за квартал',
			caption: 'Картинка из новости через медиапрокси',
			size: 'sm',
			source_ids: ['s1']
		},
		PICTURE
	),
	artifact('i2', 'image', {
		source: 'document_page',
		logo_base: null,
		url: null,
		document_id: null,
		page: 12,
		alt: 'Страница презентации',
		caption: 'Прокси не отдал страницу: заглушка ошибки',
		size: 'sm',
		source_ids: []
	})
];

export const ARTIFACTS: ArtifactOut[] = [
	artifact('c1', 'chart', CHARTS[2] as ChartSpec),
	artifact('t1', 'table', TABLE),
	...IMAGES.slice(0, 1)
];

export const SOURCES: SourceRef[] = [
	{
		local_id: 's1',
		kind: 'web',
		title: 'Банк отчитался за второй квартал',
		url: 'https://example.com/news/bank-q2',
		publisher: 'example.com',
		published_at: '2026-07-29',
		document_id: null,
		page: null,
		snippet: 'Чистая прибыль выросла на 9 % год к году, рентабельность капитала составила 24 %.'
	},
	{
		local_id: 's2',
		kind: 'tinvest',
		title: 'Календарь дивидендов Т-Инвестиций',
		url: null,
		publisher: 'Т-Инвестиции',
		published_at: null,
		document_id: null,
		page: null,
		snippet: null
	},
	{
		local_id: 's3',
		kind: 'edisclosure',
		title: 'Отчётность МСФО за 6 месяцев 2026 года',
		url: 'https://www.e-disclosure.ru/portal/files.aspx?id=3043&type=4',
		publisher: 'e-disclosure',
		published_at: '2026-08-28',
		document_id: null,
		page: 14,
		snippet: null
	}
];

export const MARKDOWN = [
	'### Итог по портфелю',
	'',
	'Портфель вырос на **3,2 %** за месяц [s1]. Дивиденды пришли по двум бумагам [s2], отчётность эмитента лежит на e-disclosure [s3]. Сноска без источника скрыта [s9].',
	'',
	'- Крупнейшая позиция: SBER',
	'- Облигации дают стабильный купон',
	'',
	'| Бумага | Доля |',
	'|---|---|',
	'| SBER | 32 % |',
	'| GAZP | 18 % |',
	'',
	'```ts',
	'const weight = value / total;',
	'```',
	'',
	'Внешняя ссылка: [пример](https://example.com). Опасный ввод остаётся текстом: <script>window.hacked = true</script> <img src="x" onerror="window.hacked = true"> [ссылка](javascript:alert(1)) ![картинка](https://example.com/a.png)'
].join('\n');

export const USER: UserOut = {
	id: '5b0d8f3e-2a61-4e4b-9d7c-7c1f2e8a9b10',
	email: 'demo@example.test',
	display_name: 'Демо',
	role: 'user',
	created_at: '2026-09-26T10:00:00Z'
};

export const ACCOUNTS: BrokerAccountOut[] = [
	{
		alias: 'acc1',
		name: 'Брокерский',
		type: 'broker',
		status: 'open',
		opened_at: '2021-04-12',
		is_hidden: false
	},
	{
		alias: 'acc2',
		name: 'ИИС',
		type: 'iis',
		status: 'open',
		opened_at: '2023-01-30',
		is_hidden: false
	},
	{
		alias: 'acc3',
		name: 'Инвесткопилка',
		type: 'invest_box',
		status: 'open',
		opened_at: '2024-06-01',
		is_hidden: true
	}
];

export const ERROR: ApiError = {
	code: 'tinvest_unavailable',
	message: 'Т-Инвестиции недоступны, попробуйте позже',
	details: null,
	request_id: 'req-7f3a2c',
	status: 503
};
