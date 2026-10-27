# DQ Монитор ошибок — пакет внедрения

Дашборд ошибок качества данных в Superset 7 на витринах StarRocks. Источник — журнал `dq.issue_journal`, который заполняют правила UMIDA. Макет: «DQ Монитор ошибок» (claude.ai), ТЗ: «ТЗ: дашборд DQ Монитор ошибок в Superset 7».

## Состав

| Файл | Что это |
| --- | --- |
| `sql/01_ddl.sql` | Таблицы `dq.issue_registry`, `dq.agg_issue_daily`, `dq.report_dependency`; виды `dq.v_issue_person`, `dq.v_rule_pass`, `dq.v_issue_report` |
| `sql/02_issue_registry.sql` | Пересборка реестра ошибок (жизненный цикл) из журнала |
| `sql/03_agg_issue_daily.sql` | Дневной агрегат за 13 месяцев |
| `airflow/dq_monitor_marts.py` | DAG Airflow 3: ждёт прогона правил UMIDA → реестр → агрегат → сверка итогов |
| `superset/dq_monitor_dashboard.zip` | Пакет импорта Superset: подключение, 6 датасетов, 49 чартов, дашборд с 9 вкладками, 9 нативными фильтрами и кросс-фильтрами |
| `superset/set_database_uuid.py` | Привязать пакет к существующему подключению StarRocks |
| `superset/superset_config_dq.py` | Фрагмент конфига: feature flags, тема и цветовая схема Kapitalbank |
| `superset/rls_rules.json` | Правила Row Level Security по ролям |
| `build_superset_bundle.py` | Генератор пакета (правки — здесь, затем пересборка) |
| `validate_bundle.py` | Проверка ссылок пакета: датасеты, метрики, колонки, позиции, фильтры |

## Порядок установки

1. **Маппинг таблиц.** Замените условные имена на реальные во всех SQL (поиском по `umida.` и `dds.`):

   | В пакете | Что должно быть | Нужные поля |
   | --- | --- | --- |
   | `umida.dq_rule` | правила DQ | `id` (UUID), `code`, `name`, `threshold_pct` |
   | `umida.dq_rule_run` | запуски правил | `id`, `rule_id`, `started_at`, `status`, `total_records`, `failed_records` |
   | `umida.dq_issue_exception` | принятые исключения | `issue_key`, `reason`, `decided_by`, `decided_at` |
   | `umida.dict_data_domain` | домены | `id`, `short_name`, `parent_id`, `business_owner_name` |
   | `umida.dict_data_domain_steward` | стюарды домена | `domain_id`, `full_name` |
   | `umida.dict_data_product` | дата-продукты | `id`, `name` |
   | `umida.org_unit` | подразделения | `id`, `name` |
   | `dds.dim_calendar` | календарь | `dt` |
   | `dds.dim_employee` | сотрудники (1С ЗУП + AD) | `login`, `full_name`, `branch_name`, `tobo_id`, `org_unit_id`, `status` |
   | `dq.v_user_domain` | домены, где пользователь владелец или стюард | `login`, `domain_id` |

2. **StarRocks.** Выполнить `sql/01_ddl.sql`, затем один раз `02_issue_registry.sql` и `03_agg_issue_daily.sql`. Заполнить `dq.report_dependency`.
3. **Airflow.** Положить `airflow/dq_monitor_marts.py` и папку `sql/` рядом (DAG читает `sql/02…`, `sql/03…`). Подключение `starrocks_dwh` — MySQL-протокол FE, порт 9030.
4. **Superset — конфиг.** Добавить `superset/superset_config_dq.py` в `superset_config.py`, положить логотип, перезапустить. Без `ENABLE_TEMPLATE_PROCESSING` виртуальные датасеты не работают.
5. **Superset — импорт.**
   - Если подключение к StarRocks уже есть: `python superset/set_database_uuid.py <uuid подключения>` и импортировать полученный архив.
   - Иначе импортировать `dq_monitor_dashboard.zip` как есть и ввести пароль пользователя `superset_ro` (строка подключения в пакете: `starrocks://superset_ro@starrocks-fe:9030/default_catalog.dq`).
   - Импорт: Дашборды → Импорт (иконка ⤒) или `superset import-dashboards -p dq_monitor_dashboard.zip -u admin`.
6. **Доступы.** Создать роли `DQ_Admin`, `DQ_Management`, `DQ_DomainOwner`, `DQ_ResponsibleUnit`, `DQ_Branch`, `DQ_Employee`, выдать доступ к датасетам и дашборду, завести RLS из `superset/rls_rules.json`.
7. **Проверка** — критерии приёмки в ТЗ.

## Как устроен дашборд

- **Период.** Нативный фильтр «Период» (по умолчанию 90 дней). Дата отчёта = последний день периода: на неё считаются все «открыто / просрочено / на дату», линейные графики показывают весь период. Это реализовано через `get_time_filter` в виртуальных датасетах `dq_*_on_date`.
- **Кросс-фильтры** включены на всех чартах: клик по столбцу или строке фильтрует весь дашборд. Колонка кросс-фильтра должна быть в датасете чарта — поэтому разрезы называются одинаково во всех датасетах (`tobo_name`, `rule_name`, `domain_name`, `data_product_name`, `responsible_unit_name`, `login`).
- **Роль сотрудника** — обязательный фильтр, действует только на чарты датасета `dq_person_on_date` (по умолчанию «Ответственный»).
- **Статус ошибки** — только для вкладки «Журнал ошибок» (по умолчанию открытые статусы).

## Отличия от макета

| В макете | В Superset | Почему |
| --- | --- | --- |
| Δ за 7 дней в штуках на Big Number | Big Number показывает Δ в процентах | так устроено сравнение периодов в Big Number; Δ в штуках есть в таблицах |
| Медиана исправления в таблицах разрезов | Среднее время исправления | медиана не складывается из дневного агрегата; медиана — на Big Number «Обзора» |
| Ряд из 6 показателей на каждой вкладке | Только на «Обзоре» | в Superset чарт стоит на дашборде один раз; кросс-фильтр с любой вкладки меняет и «Обзор» |
| Линейный график на вкладке «Сотрудники» | Нет | агрегат по дням хранит только ответственного, роли — в `dq_person_on_date` на дату |
| Ошибки дочерних доменов внутри родителя | Фильтр «Родительский домен» и колонка в таблице доменов | кросс-фильтр работает по точному домену |
| Регион отделения | Нет | нет в журнале; добавить в `dds.dim_tobo` и агрегат при необходимости |

## Что проверить после импорта

- Версия Superset: пакет в формате экспорта v1.0.0; проверен структурно (`validate_bundle.py`), на живом Superset 7 не импортировался. Если импорт ругается на параметр чарта — откройте чарт, сохраните его заново в Explore.
- Сортировка топ-10 по сумме серий (`x_axis_sort_series`) появилась в Superset 3.1; в 7-й версии должна работать.
- Ссылка «Открыть ↗» в таблице правил использует `allow_render_html` таблицы.
