"""Execute the saved SQL, independently reconcile results, and build report figures."""
import json
import sqlite3
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from generate_data import ROOT, END


def build_database(frames):
    database = ROOT / 'data' / 'ecommerce.sqlite'
    database.unlink(missing_ok=True)
    con = sqlite3.connect(database)
    con.executescript((ROOT / 'sql' / 'schema.sql').read_text())
    for name, df in frames.items():
        df.to_sql(name, con, if_exists='append', index=False)
    con.commit()
    return con


def validate(con, frames, results):
    """Independent pandas calculations for every analytical SQL output."""
    u, e, o = (frames[x] for x in ('users', 'events', 'orders'))
    assert not con.execute('PRAGMA foreign_key_check').fetchall()
    assert all(not df.iloc[:, 0].duplicated().any() for df in frames.values())
    assert e.user_id.isin(u.user_id).all() and o.user_id.isin(u.user_id).all()
    assert pd.to_datetime(e.event_time).max().normalize() <= END
    assert (pd.to_datetime(e.event_time) >= pd.to_datetime(e.user_id.map(u.set_index('user_id').signup_date))).all()
    purchased = e[e.event_name.eq('purchase')].sort_values('session_id')
    paid = o.sort_values('session_id')
    assert purchased.session_id.tolist() == paid.session_id.tolist()
    assert purchased.user_id.tolist() == paid.user_id.tolist()
    assert purchased.event_time.tolist() == paid.order_time.tolist()
    assert (o.amount_kzt > 0).all()
    f = e.pivot(index='session_id', columns='event_name', values='event_time')
    meta = e[e.event_name.eq('view')].set_index('session_id')[['user_id','platform','app_version']]
    f = f.join(meta)
    for earlier, later in zip(['view','add_to_cart','checkout'], ['add_to_cart','checkout','purchase']):
        used = f[later].notna()
        assert f.loc[used, earlier].notna().all()
        assert (f.loc[used, later] > f.loc[used, earlier]).all()
    counts = [int(f[x].notna().sum()) for x in ['view','add_to_cart','checkout','purchase']]
    assert results['01_funnel'].sessions.tolist() == counts
    np.testing.assert_allclose(results['01_funnel'].conversion_from_view, np.array(counts)/counts[0])
    np.testing.assert_allclose(results['01_funnel'].conversion_from_previous, [1] + [b/a for a,b in zip(counts, counts[1:])])
    active = e.assign(day=pd.to_datetime(e.event_time).dt.normalize())[['user_id','day']].drop_duplicates()
    for row in results['02_activity'].itertuples():
        day = pd.Timestamp(row.day)
        for field, window in [('dau',1),('wau',7),('mau',30)]:
            expected = active.loc[active.day.between(day-pd.Timedelta(days=window-1),day),'user_id'].nunique()
            assert getattr(row,field) == expected
    cohorts = u.assign(signup=pd.to_datetime(u.signup_date))
    cohorts['cohort'] = cohorts.signup.dt.strftime('%Y-%m')
    cohorts['cohort_week'] = (cohorts.signup - pd.to_timedelta(cohorts.signup.dt.dayofweek,unit='D')).dt.strftime('%Y-%m-%d')
    for query, field in [('03_retention','cohort'),('08_weekly_cohorts','cohort_week')]:
        for row in results[query].itertuples():
            group = cohorts[cohorts[field].eq(getattr(row,field))].copy()
            group['target'] = group.signup + pd.Timedelta(days=row.day_number)
            group = group[group.target <= END]
            returned = group.merge(active,left_on=['user_id','target'],right_on=['user_id','day'])
            assert row.eligible_users == len(group) and row.retained_users == len(returned)
            assert np.isclose(row.retention, len(returned)/len(group))
    for row in results['04_revenue'].itertuples():
        group = o[o.order_time.str.startswith(row.month)]
        assert row.paid_orders == len(group) and row.buyers == group.user_id.nunique()
        assert row.revenue_kzt == group.amount_kzt.sum()
        assert np.isclose(row.average_order_value_kzt, group.amount_kzt.mean())
    buyer_days = o.assign(day=pd.to_datetime(o.order_time).dt.normalize()).sort_values(['user_id','order_time']).groupby('user_id').day.agg(list)
    eligible = buyer_days[buyer_days.map(lambda ds: ds[0]+pd.Timedelta(days=30) <= END)]
    repeats = sum(len(ds)>1 and ds[1]<=ds[0]+pd.Timedelta(days=30) for ds in eligible)
    row = results['05_repeat_purchase'].iloc[0]
    assert row.eligible_buyers == len(eligible) and row.repeat_buyers_30d == repeats
    assert np.isclose(row.repeat_purchase_rate_30d,repeats/len(eligible))
    for row in results['06_segments'].itertuples():
        g = f[f['view'].str.startswith(row.month) & f.platform.eq(row.platform) & f.app_version.eq(row.app_version)]
        assert row.sessions == len(g) and row.carts == g.add_to_cart.notna().sum()
        assert row.checkouts == g.checkout.notna().sum() and row.purchases == g.purchase.notna().sum()
        assert np.isclose(row.checkout_conversion, g.purchase.notna().sum()/g.checkout.notna().sum())
        assert np.isclose(row.session_conversion, g.purchase.notna().sum()/len(g))
    for row in results['07_channels'].itertuples():
        ids = u[u.acquisition_channel.eq(row.acquisition_channel)].user_id
        group = o[o.user_id.isin(ids)]
        assert row.users == len(ids) and row.buyers == group.user_id.nunique()
        assert row.paid_orders == len(group) and row.revenue_kzt == group.amount_kzt.sum()
        assert np.isclose(row.user_purchase_conversion,group.user_id.nunique()/len(ids))
        assert np.isclose(row.revenue_per_registered_user_kzt,group.amount_kzt.sum()/len(ids))
    for row in results['09_payment_errors'].itertuples():
        g = f[f['view'].str.startswith(row.month) & f.platform.eq(row.platform) & f.app_version.eq(row.app_version) & f.checkout.notna()]
        assert row.checkout_sessions == len(g) and row.error_sessions == g.payment_error.notna().sum()
        assert np.isclose(row.payment_error_rate, g.payment_error.notna().sum()/len(g))
    return {'status':'passed', 'sql_outputs_reconciled':len(results), 'users':len(u),'events':len(e),'orders':len(o),
            'checks':['Primary/foreign keys','Dates and positive order amounts','Purchase-event/order bijection',
                      'Ordered session funnel','Independent pandas reconciliation of all 9 SQL results',
                      'Exact-day retention and fully observed repeat buyers']}


def figures(results):
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,
                         'axes.titlesize':13,'axes.labelsize':10,'figure.dpi':160})
    output = ROOT / 'reports' / 'figures'
    output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2,2,figsize=(12,8),layout='constrained')
    funnel = results['01_funnel']
    axes[0,0].barh(funnel.event_name[::-1],funnel.sessions[::-1],color='#3576A8')
    axes[0,0].set_title('Session funnel | June–September 2026')
    axes[0,0].set_xlabel('Sessions')
    for i, n in enumerate(funnel.sessions[::-1]):
        axes[0,0].text(n+100,i,f'{n:,}',va='center',fontsize=9)
    axes[0,0].set_xlim(0,funnel.sessions.max()*1.2)
    seg = results['06_segments']
    grouped = seg.groupby(['month','platform'])[['checkouts','purchases']].sum().reset_index()
    for platform, group in grouped.groupby('platform'):
        axes[0,1].plot(group.month,100*group.purchases/group.checkouts,marker='o',label=platform)
    axes[0,1].set(title='Checkout → purchase by platform',ylabel='Conversion (%)',ylim=(0,100))
    axes[0,1].legend(frameon=False)
    revenue = results['04_revenue']
    axes[1,0].bar(revenue.month,revenue.revenue_kzt/1_000_000,color='#2A8C7F')
    axes[1,0].set(title='Paid revenue',ylabel='Million KZT')
    activity = results['02_activity']
    dates = pd.to_datetime(activity.day)
    for col in ['dau','wau','mau']:
        axes[1,1].plot(dates,activity[col],label=col.upper())
    axes[1,1].set(title='Daily activity | rolling 7 / 30 days',ylabel='Unique active users')
    axes[1,1].legend(frameon=False)
    axes[1,1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1,1].xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    axes[1,1].set_xlim(dates.min(),dates.max())
    fig.suptitle('E-commerce product analytics | SYNTHETIC DATA',fontsize=17,fontweight='bold')
    fig.savefig(output/'overview.png',bbox_inches='tight')
    plt.close(fig)
    matrix = results['08_weekly_cohorts'].pivot(index='cohort_week',columns='day_number',values='retention')
    fig, ax = plt.subplots(figsize=(8,7),layout='constrained')
    im = ax.imshow(matrix.values*100,cmap='Blues',vmin=0,vmax=100,aspect='auto')
    ax.set_xticks(range(len(matrix.columns)),[f'D{x}' for x in matrix.columns])
    sizes = results['08_weekly_cohorts'].query('day_number == 0').set_index('cohort_week').eligible_users
    ax.set_yticks(range(len(matrix.index)),[f'{week} (n={sizes.loc[week]})' for week in matrix.index])
    ax.set(title='Exact-day retention by signup week | synthetic data',xlabel='Days since signup',ylabel='Cohort week (Monday)')
    for y in range(len(matrix)):
        for x in range(len(matrix.columns)):
            value = matrix.iloc[y,x]*100
            ax.text(x,y,f'{value:.1f}%',ha='center',va='center',color='white' if value>60 else '#12243A',fontsize=9)
    fig.colorbar(im,ax=ax,label='Retention (%)')
    fig.savefig(output/'cohorts.png',bbox_inches='tight')
    plt.close(fig)


def report(frames, results):
    f = results['01_funnel']
    seg = results['06_segments']
    bad = seg[(seg.month=='2026-09') & (seg.app_version=='2.1')].iloc[0]
    ref = seg[(seg.month=='2026-09') & (seg.platform=='android') & (seg.app_version=='2.0')].iloc[0]
    gap = ref.checkout_conversion-bad.checkout_conversion
    opportunity = bad.checkouts*gap
    revenue = results['04_revenue']
    aov = revenue.iloc[-1].average_order_value_kzt
    retention = results['03_retention'].groupby('day_number')[['eligible_users','retained_users']].sum()
    repeat = results['05_repeat_purchase'].iloc[0]
    text = f'''# Результаты анализа

Учебный проект на синтетических данных, seed=42. Период: 01.06–30.09.2026, UTC.
Никакие показатели не относятся к реальному магазину. Аномалия заранее задана в генераторе.

## Основные показатели

| Показатель | Значение |
|---|---:|
| Зарегистрированные пользователи | {len(frames['users']):,} |
| События | {len(frames['events']):,} |
| Сессии с просмотром | {int(f.iloc[0].sessions):,} |
| Оплаченные заказы | {len(frames['orders']):,} |
| Конверсия сессии в покупку | {f.iloc[-1].conversion_from_view:.2%} |
| Выручка, ₸ | {int(frames['orders'].amount_kzt.sum()):,} |
| Средний чек, ₸ | {frames['orders'].amount_kzt.mean():,.0f} |
| D1 retention — возврат на 1-й день | {retention.loc[1].retained_users/retention.loc[1].eligible_users:.2%} |
| D7 retention — возврат на 7-й день | {retention.loc[7].retained_users/retention.loc[7].eligible_users:.2%} |
| D30 retention — возврат на 30-й день | {retention.loc[30].retained_users/retention.loc[30].eligible_users:.2%} |
| Повторная покупка за 30 дней | {repeat.repeat_purchase_rate_30d:.2%} |

## Где обнаружена проблема

В сентябре конверсия checkout → purchase для Android 2.1 составила **{bad.checkout_conversion:.2%}**
({int(bad.purchases)} покупок / {int(bad.checkouts)} оформлений).
Для Android 2.0 в том же месяце — **{ref.checkout_conversion:.2%}**
({int(ref.purchases)} / {int(ref.checkouts)}). Разрыв — **{gap*100:.2f} п.п.**
Платформы и версии нужно смотреть отдельно: средняя конверсия скрывает проблемный сегмент.
Сравнение по месяцам и версии — в `tables/06_segments.csv`, ошибки оплаты — в `tables/09_payment_errors.csv`.

Это описательное сравнение, а не доказательство причинности. В реальных данных версии
могут отличаться составом пользователей, устройствами, банками и источниками трафика.
В этом учебном наборе причина известна потому, что заложена в генераторе.

## Сценарная оценка приоритета

Если Android 2.1 достигнет наблюдаемой сентябрьской конверсии Android 2.0 при том же
числе checkout, получится около **{opportunity:.0f} дополнительных заказов**:
`{int(bad.checkouts)} × ({ref.checkout_conversion:.4f} − {bad.checkout_conversion:.4f})`.
При среднем сентябрьском чеке {aov:,.0f} ₸ это около **{opportunity*aov/1_000_000:.2f} млн ₸**.
Это сценарий для приоритизации, не прогноз эффекта: чек сегмента может отличаться,
а часть заказов могла бы вернуться позднее. Выручка не равна прибыли.

## Продуктовые гипотезы

1. **Оплата в Android 2.1.** Сначала проверить логи SDK, коды ошибок и воспроизведение
   на устройствах. Подтверждённый дефект исправить и проверить выпуск поэтапно.
   Если предлагается новый платёжный интерфейс, проверить его экспериментом;
   основной показатель — доля пользователей с покупкой среди начавших checkout
   за фиксированные 7 дней. Контроль — предыдущий интерфейс, рандомизация по user_id.
   Защитные показатели: ошибки оплаты, средний чек, дубли списаний, время оплаты.
   Число участников и длительность рассчитываются до запуска по базовой конверсии и MDE
   (minimum detectable effect — минимальный обнаруживаемый эффект). A/B-тест здесь не проводился.
2. **Корзина.** На переходе view → add_to_cart теряется
   {(1-f.iloc[1].conversion_from_previous):.1%} сессий. Это самый большой численный отсев,
   но не доказанный дефект: просмотр не всегда означает намерение купить.
   Проверить доступность товара, стоимость доставки и поведение по категориям;
   затем тестировать показ полной стоимости раньше. Метрика — покупка на пользователя,
   защитные — средний чек и маржинальность.
3. **Возврат покупателей.** Проверить напоминание о повторной покупке для подходящих
   категорий. Метрика — повторная покупка за 30 дней среди покупателей с полным окном,
   защитные — отписки и доля покупок только со скидкой. В наборе нет категорий товаров
   или коммуникаций, поэтому это идея для следующего исследования.

## Проверка расчётов

Все девять SQL-выгрузок сверены с независимыми расчётами pandas: воронка, активность,
retention, выручка, повторные покупки, сегменты, каналы и ошибки. Проверены ключи,
даты, порядок этапов и соответствие каждой покупки одному оплаченному заказу.
Отдельные тесты проверяют неполные окна наблюдения и события в неправильном порядке.
Результат автоматических проверок: `validation.json`. Суммы выручки сверяются точно,
доли и средние — с численной погрешностью; все headline-метрики рассчитаны из данных.

## Ограничения

Набор моделирует зарегистрированных пользователей, один визит в сутки и не более одного
заказа на сессию. Нет гостей, возвратов, себестоимости, маркетинговых затрат и товарных категорий.
Поэтому нельзя оценить CAC, ROAS, прибыль или реальный LTV. Позднее зарегистрированные
пользователи имеют меньше времени для покупки: сравнение каналов за весь период смещено
разной длительностью наблюдения. Ранняя WAU/MAU имеет укороченное окно, поскольку до 1 июня
данных нет. Сессионные наблюдения одного пользователя зависимы, статистические p-value не рассчитаны.
'''
    (ROOT/'reports'/'findings.md').write_text(text,encoding='utf-8')


def analyze(frames):
    output = ROOT / 'reports' / 'tables'
    output.mkdir(parents=True, exist_ok=True)
    with build_database(frames) as con:
        results = {}
        for path in sorted((ROOT/'sql').glob('[0-9]*.sql')):
            df = pd.read_sql_query(path.read_text(),con)
            df.to_csv(output/f'{path.stem}.csv',index=False)
            results[path.stem] = df
        checks = validate(con,frames,results)
    (ROOT/'reports'/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    figures(results)
    report(frames,results)
    return checks
