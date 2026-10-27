"""
Генератор пакета импорта Superset для дашборда «DQ Монитор ошибок».
Формат: Superset assets export v1.0.0 (Настройки → Импорт дашбордов, или `superset import-dashboards`).
Запуск: python build_superset_bundle.py  → superset/dq_monitor_dashboard.zip
"""
import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

NS = uuid.UUID("5b0e3c1a-7f1d-4d6b-9a77-2f0e6d8c4a11")
U = lambda name: str(uuid.uuid5(NS, name))
OUT = Path(__file__).parent / "superset"
ROOT = "dq_monitor_export"
DB_UUID = U("database:dwhstarrocks")

# ---------------------------------------------------------------- database
database = {
    "database_name": "dwhstarrocks",
    "sqlalchemy_uri": "starrocks://superset_ro:XXXXXXXXXX@starrocks-fe:9030/default_catalog.dq",
    "cache_timeout": None,
    "expose_in_sqllab": True,
    "allow_run_async": False,
    "allow_ctas": False,
    "allow_cvas": False,
    "allow_dml": False,
    "allow_file_upload": False,
    "extra": {"allows_virtual_table_explore": True, "metadata_params": {}, "engine_params": {}, "schemas_allowed_for_file_upload": []},
    "impersonate_user": False,
    "uuid": DB_UUID,
    "version": "1.0.0",
}

# ---------------------------------------------------------------- datasets
def col(name, typ="VARCHAR", verbose=None, dttm=False):
    return {"column_name": name, "verbose_name": verbose, "is_dttm": dttm, "is_active": True, "type": typ,
            "advanced_data_type": None, "groupby": not dttm or True, "filterable": True, "expression": None,
            "description": None, "python_date_format": None, "extra": {}}

def met(name, expr, verbose, fmt=None, desc=None):
    return {"metric_name": name, "verbose_name": verbose, "metric_type": None, "expression": expr,
            "description": desc, "d3format": fmt, "currency": None, "extra": {}, "warning_text": None}

def dataset(name, cols, metrics, sql=None, schema="dq", dttm="report_date", desc=None):
    return {"table_name": name, "main_dttm_col": dttm, "description": desc, "default_endpoint": None, "offset": 0,
            "cache_timeout": None, "catalog": None, "schema": schema, "sql": sql, "params": None, "template_params": None,
            "filter_select_enabled": True, "fetch_values_predicate": None, "extra": None, "normalize_columns": False,
            "always_filter_main_dttm": False, "uuid": U("dataset:" + name), "metrics": metrics, "columns": cols,
            "version": "1.0.0", "database_uuid": DB_UUID}

V = {  # подписи колонок
    "report_date": "Дата отчёта", "tobo_id": "Код отделения", "tobo_name": "Отделение", "rule_code": "Правило", "rule_name": "Наименование правила",
    "domain_name": "Домен", "parent_domain_name": "Родительский домен", "business_owner": "Бизнес-владелец", "stewards": "Стюарды",
    "data_product_name": "Дата-продукт", "responsible_unit_name": "Ответственное подразделение", "entity_type": "entity_type",
    "object_type": "Тип объекта", "source_name": "Система-источник", "severity": "Важность", "responsible_login": "Ответственный",
    "object_id": "ID объекта", "object_name": "Объект", "field_name": "Поле", "actual_value": "Сейчас", "expected_value": "Должно быть",
    "error_type": "Тип ошибки", "error": "Описание", "information": "Доп. информация", "created_by_login": "Создал",
    "executed_by_login": "Провёл", "modified_by_login": "Изменил", "manager_login": "Менеджер", "first_seen_date": "Обнаружена",
    "due_date": "Срок", "closed_date": "Закрыта", "status_on_date": "Статус ошибки", "exception_reason": "Причина исключения",
    "exception_by": "Исключение принял", "issue_key": "issue_key", "error_code": "error_code", "dimension": "dimension",
    "amount": "Сумма, сум", "role": "Роль сотрудника", "login": "Сотрудник", "employee_name": "ФИО сотрудника",
    "employee_branch": "Отделение сотрудника", "employee_status": "Статус сотрудника", "report_name": "Отчёт", "report_type": "Тип отчёта",
    "responsible_name": "ФИО ответственного", "responsible_status": "Статус ответственного", "run_date": "Дата запуска",
    "umida_link": "Правило в UMIDA",
}
def cols_of(names, dttm=("report_date",), types=None):
    types = types or {}
    out = []
    for n in names:
        is_d = n in dttm or n.endswith("_date")
        out.append(col(n, types.get(n, "DATE" if is_d else "VARCHAR"), V.get(n), dttm=n in dttm))
    return out

AGG_DIMS = ["tobo_id", "tobo_name", "rule_code", "rule_name", "domain_name", "parent_domain_name", "business_owner",
            "data_product_name", "responsible_unit_name", "entity_type", "object_type", "source_name", "severity", "responsible_login"]
AGG_NUMS = ["open_cnt", "open_overdue_cnt", "new_cnt", "closed_cnt", "closed_late_cnt", "fixed_cnt", "new_7d_cnt", "fixed_7d_cnt",
            "exception_7d_cnt", "open_7d_ago_cnt", "overdue_7d_ago_cnt", "fixed_30d_cnt", "fix_days_30d_sum", "open_amount"]

AGG_METRICS = [
    met("open", "SUM(open_cnt)", "Открытые", ",d"),
    met("overdue", "SUM(open_overdue_cnt)", "Открытые просроченные", ",d"),
    met("in_time", "SUM(open_cnt) - SUM(open_overdue_cnt)", "Открытые в срок", ",d"),
    met("overdue_pct", "SUM(open_overdue_cnt) / NULLIF(SUM(open_cnt), 0)", "Доля просроченных", ".1%"),
    met("crit", "SUM(CASE WHEN severity = 'Критический' THEN open_cnt ELSE 0 END)", "Критичных", ",d"),
    met("new_day", "SUM(new_cnt)", "Новые", ",d"),
    met("closed", "SUM(closed_cnt)", "Закрытые", ",d"),
    met("closed_late", "SUM(closed_late_cnt)", "Закрытые с просрочкой", ",d"),
    met("new_7d", "SUM(new_7d_cnt)", "Новые за 7 дней", ",d"),
    met("fixed_7d", "SUM(fixed_7d_cnt)", "Исправлено за 7 дней", ",d"),
    met("exc_7d", "SUM(exception_7d_cnt)", "В исключения за 7 дней", ",d"),
    met("delta_open_7d", "SUM(open_cnt) - SUM(open_7d_ago_cnt)", "Δ открытых за 7 дней", "+,d"),
    met("delta_overdue_7d", "SUM(open_overdue_cnt) - SUM(overdue_7d_ago_cnt)", "Δ просроченных за 7 дней", "+,d"),
    met("avg_fix_days", "SUM(fix_days_30d_sum) / NULLIF(SUM(fixed_30d_cnt), 0)", "Среднее время исправления, дн.", ",.1f"),
    met("open_amount", "SUM(open_amount)", "Сумма под риском, сум", ",.0f"),
]

TF = "{% set tf = get_time_filter('report_date', remove_filter=True, target_type='DATE') %}"
ON_DATE = """with d as (
    select coalesce(max(report_date), current_date()) as dt
    from dq.agg_issue_daily
    {% if tf.to_expr %}where report_date < {{ tf.to_expr }}{% endif %}
)"""

ds_daily = dataset("agg_issue_daily", cols_of(["report_date"] + AGG_DIMS) +
                   [col(n, "BIGINT") for n in AGG_NUMS], AGG_METRICS,
                   desc="Дневной агрегат ошибок: динамика по дням (физическая таблица dq.agg_issue_daily).")

ds_ondate = dataset("dq_agg_on_date", cols_of(["report_date"] + AGG_DIMS) + [col(n, "BIGINT") for n in AGG_NUMS], AGG_METRICS,
    sql=f"""{TF}
{ON_DATE}
select a.*
from dq.agg_issue_daily a
join d on a.report_date = d.dt""",
    desc="Агрегат на дату отчёта: последний день внутри фильтра «Период».")

REG_COLS = ["issue_key", "rule_code", "rule_name", "domain_name", "parent_domain_name", "business_owner", "data_product_name",
            "responsible_unit_name", "dimension", "severity", "tobo_id", "tobo_name", "source_name", "object_type", "object_id",
            "object_name", "field_name", "actual_value", "expected_value", "error_type", "error", "information", "created_by_login",
            "executed_by_login", "modified_by_login", "manager_login", "responsible_login", "entity_type", "error_code", "amount",
            "first_seen_date", "due_date", "closed_date", "exception_reason", "exception_by"]

ds_issues = dataset("dq_issues_on_date",
    cols_of(["report_date"] + REG_COLS + ["status_on_date", "responsible_name", "responsible_status"], types={"amount": "DECIMAL"}) +
    [col("fix_days_30d", "INT")],
    [met("cnt", "COUNT(*)", "Ошибок", ",d"),
     met("median_fix_days", "PERCENTILE_APPROX(fix_days_30d, 0.5)", "Медиана исправления, дн.", ",.0f"),
     met("amount_sum", "SUM(amount)", "Сумма, сум", ",.0f")],
    sql=f"""{TF}
{ON_DATE}
select r.*,
       d.dt as report_date,
       case when r.closed_date is not null and r.closed_date <= d.dt
                 then case when r.status = 'Исключение' then 'Исключение' else 'Исправлена' end
            when d.dt > r.due_date then 'Просрочена'
            when datediff(d.dt, r.first_seen_date) <= 1 then 'Новая'
            else 'Открыта' end                                                   as status_on_date,
       case when r.status = 'Исправлена' and r.closed_date between date_sub(d.dt, 29) and d.dt
            then r.fix_days_actual end                                           as fix_days_30d,
       e.full_name                                                               as responsible_name,
       e.status                                                                  as responsible_status
from dq.issue_registry r
cross join d
left join dds.dim_employee e on e.login = r.responsible_login
where r.first_seen_date <= d.dt""",
    desc="Ошибки с их статусом на дату отчёта: таблицы ошибок и журнал.")

PERSON_EXTRA = ["role", "login", "employee_name", "employee_branch", "employee_status", "status_on_date"]
PERSON_INTS = ["is_open", "is_overdue", "is_new_7d", "is_fixed_7d", "was_open_7d", "fix_days_30d"]
ds_person = dataset("dq_person_on_date",
    cols_of(["report_date"] + REG_COLS + PERSON_EXTRA, types={"amount": "DECIMAL"}) + [col(n, "INT") for n in PERSON_INTS],
    [met("open", "SUM(is_open)", "Открытые", ",d"),
     met("overdue", "SUM(is_overdue)", "Открытые просроченные", ",d"),
     met("in_time", "SUM(is_open) - SUM(is_overdue)", "Открытые в срок", ",d"),
     met("overdue_pct", "SUM(is_overdue) / NULLIF(SUM(is_open), 0)", "Доля просроченных", ".1%"),
     met("crit", "SUM(CASE WHEN severity = 'Критический' THEN is_open ELSE 0 END)", "Критичных", ",d"),
     met("new_7d", "SUM(is_new_7d)", "Новые за 7 дней", ",d"),
     met("fixed_7d", "SUM(is_fixed_7d)", "Исправлено за 7 дней", ",d"),
     met("delta_open_7d", "SUM(is_open) - SUM(was_open_7d)", "Δ открытых за 7 дней", "+,d"),
     met("avg_fix_days", "AVG(fix_days_30d)", "Среднее время исправления, дн.", ",.1f")],
    sql=f"""{TF}
{ON_DATE}
select r.*,
       p.role, p.login,
       e.full_name   as employee_name,
       e.branch_name as employee_branch,
       e.status      as employee_status,
       d.dt          as report_date,
       case when r.closed_date is not null and r.closed_date <= d.dt
                 then case when r.status = 'Исключение' then 'Исключение' else 'Исправлена' end
            when d.dt > r.due_date then 'Просрочена'
            when datediff(d.dt, r.first_seen_date) <= 1 then 'Новая'
            else 'Открыта' end                                                                       as status_on_date,
       case when r.first_seen_date <= d.dt and (r.closed_date is null or r.closed_date > d.dt) then 1 else 0 end as is_open,
       case when r.first_seen_date <= d.dt and (r.closed_date is null or r.closed_date > d.dt)
                 and d.dt > r.due_date then 1 else 0 end                                             as is_overdue,
       case when r.first_seen_date between date_sub(d.dt, 6) and d.dt then 1 else 0 end              as is_new_7d,
       case when r.status = 'Исправлена' and r.closed_date between date_sub(d.dt, 6) and d.dt then 1 else 0 end as is_fixed_7d,
       case when r.first_seen_date <= date_sub(d.dt, 7)
                 and (r.closed_date is null or r.closed_date > date_sub(d.dt, 7)) then 1 else 0 end   as was_open_7d,
       case when r.status = 'Исправлена' and r.closed_date between date_sub(d.dt, 29) and d.dt
            then r.fix_days_actual end                                                               as fix_days_30d
from dq.v_issue_person p
join dq.issue_registry r on r.issue_key = p.issue_key
cross join d
left join dds.dim_employee e on e.login = p.login
where r.first_seen_date <= d.dt
  and (r.closed_date is null or r.closed_date >= date_sub(d.dt, 29))""",
    desc="Ошибка × роль сотрудника на дату отчёта. Всегда используйте с фильтром «Роль сотрудника».")

ds_pass = dataset("v_rule_pass",
    cols_of(["run_date", "rule_code", "rule_name", "umida_link"], dttm=("run_date",)) +
    [col("rule_id", "VARCHAR"), col("run_id", "VARCHAR"), col("total_records", "BIGINT"), col("failed_records", "BIGINT"),
     col("pass_rate", "DOUBLE"), col("threshold", "DOUBLE")],
    [met("pass_rate", "AVG(pass_rate)", "Процент прохождения", ".2%"),
     met("threshold", "MAX(threshold)", "Порог правила", ".2%"),
     met("pass_rate_last", "MAX_BY(pass_rate, run_date)", "% прохождения (последний запуск)", ".2%"),
     met("failed_last", "MAX_BY(failed_records, run_date)", "Ошибок в последнем запуске", ",d"),
     met("total_last", "MAX_BY(total_records, run_date)", "Проверено записей", ",d")],
    dttm="run_date", desc="Запуски правил UMIDA: процент прохождения и порог.")

ds_report = dataset("dq_report_on_date",
    cols_of(["report_date", "report_name", "report_type", "rule_code", "rule_name", "object_type", "domain_name", "severity",
             "tobo_name", "source_name", "object_name", "error", "responsible_login", "due_date", "status_on_date", "issue_key"]) +
    [col("amount", "DECIMAL"), col("is_overdue", "INT")],
    [met("open", "COUNT(*)", "Открытых ошибок", ",d"),
     met("crit", "SUM(CASE WHEN severity = 'Критический' THEN 1 ELSE 0 END)", "Критичные", ",d"),
     met("others", "SUM(CASE WHEN severity = 'Критический' THEN 0 ELSE 1 END)", "Остальные", ",d"),
     met("overdue", "SUM(is_overdue)", "Просрочено", ",d"),
     met("amount_sum", "SUM(amount)", "Сумма под риском, сум", ",.0f")],
    sql=f"""{TF}
{ON_DATE}
select r.report_name, r.report_type, r.rule_code, r.rule_name, r.object_type, r.domain_name, r.severity,
       r.tobo_name, r.source_name, r.object_name, r.error, r.responsible_login, r.due_date, r.issue_key, r.amount,
       d.dt as report_date,
       case when d.dt > r.due_date then 'Просрочена'
            when datediff(d.dt, r.first_seen_date) <= 1 then 'Новая' else 'Открыта' end as status_on_date,
       case when d.dt > r.due_date then 1 else 0 end                                    as is_overdue
from dq.v_issue_report r
cross join d
where r.first_seen_date <= d.dt and (r.closed_date is null or r.closed_date > d.dt)""",
    desc="Открытые ошибки × отчёты, которые строятся из этих данных.")

DATASETS = [ds_daily, ds_ondate, ds_issues, ds_person, ds_pass, ds_report]
DSU = {d["table_name"]: d["uuid"] for d in DATASETS}

# ---------------------------------------------------------------- chart builders
CHARTS = []
def chart(key, name, viz, ds, params, desc=None):
    p = {"viz_type": viz, "datasource": "__DATASOURCE__", "adhoc_filters": [], "time_range": "No filter",
         "color_scheme": "kapitalbank", **params}
    c = {"key": key, "id": len(CHARTS) + 1, "slice_name": name, "description": desc, "certified_by": None,
         "certification_details": None, "viz_type": viz, "params": p, "query_context": None, "cache_timeout": None,
         "uuid": U("chart:" + key), "version": "1.0.0", "dataset_uuid": DSU[ds], "ds": ds}
    CHARTS.append(c)
    return c

def big_number(key, name, metric, sub, fmt=",d"):
    return chart(key, name, "big_number", "agg_issue_daily", {
        "metric": metric, "x_axis": "report_date", "granularity_sqla": "report_date", "time_grain_sqla": "P1D",
        "show_trend_line": True, "start_y_axis_at_zero": True, "compare_lag": 7, "compare_suffix": sub,
        "header_font_size": 0.4, "subheader_font_size": 0.15, "y_axis_format": fmt, "time_format": "%d.%m.%Y",
        "rolling_type": "None", "aggregation": "LAST_VALUE"})

def open_closed_line(key, name):
    return chart(key, name, "mixed_timeseries", "agg_issue_daily", {
        "x_axis": "report_date", "time_grain_sqla": "P1D",
        "metrics": ["open", "overdue"], "groupby": [], "adhoc_filters": [], "rolling_type": "None", "row_limit": 10000,
        "metrics_b": ["closed", "closed_late"], "groupby_b": [], "adhoc_filters_b": [], "rolling_type_b": "cumsum", "row_limit_b": 10000,
        "seriesType": "line", "seriesTypeB": "line", "area": True, "areaB": False, "opacity": 0.1, "opacityB": 0.2,
        "markerEnabled": False, "markerEnabledB": False, "yAxisIndex": 0, "yAxisIndexB": 0,
        "show_legend": True, "legendType": "scroll", "legendOrientation": "top", "rich_tooltip": True,
        "tooltipTimeFormat": "%d.%m.%Y", "x_axis_time_format": "%d %b", "y_axis_format": "SMART_NUMBER",
        "truncate_metric": True, "zoomable": True},
        desc="Открытые — на каждую дату; закрытые — нарастающим итогом с начала периода.")

def hbar(key, name, ds, xcol, metrics, sort_metric, limit=10):
    return chart(key, name, "echarts_timeseries_bar", ds, {
        "x_axis": xcol, "metrics": metrics, "groupby": [], "orientation": "horizontal", "stack": "Stack",
        "row_limit": limit, "timeseries_limit_metric": sort_metric, "order_desc": True,
        "x_axis_sort_asc": False, "x_axis_sort_series": "sum", "x_axis_sort_series_ascending": False,
        "show_value": True, "show_legend": True, "legendOrientation": "top", "rich_tooltip": True,
        "y_axis_format": ",d", "truncateXAxis": True, "xAxisLabelRotation": 0})

def member_table(key, name, ds, dims, metrics, extra_cc=None):
    cc = {"open": {"showCellBars": True}, "overdue_pct": {"d3NumberFormat": ".1%"},
          "delta_open_7d": {"d3NumberFormat": "+,d"}, "avg_fix_days": {"d3NumberFormat": ",.1f"}}
    cc.update(extra_cc or {})
    return chart(key, name, "table", ds, {
        "query_mode": "aggregate", "groupby": dims, "metrics": metrics, "all_columns": [], "percent_metrics": [],
        "timeseries_limit_metric": "open", "order_desc": True, "row_limit": 1000, "server_pagination": False,
        "page_length": 10, "include_search": True, "show_cell_bars": True, "align_pn": False, "color_pn": True,
        "allow_rearrange_columns": True, "allow_render_html": True, "column_config": cc,
        "conditional_formatting": [{"column": "overdue", "operator": ">", "targetValue": 0, "colorScheme": "#D92D20"}]})

OPEN_ONLY = {"expressionType": "SIMPLE", "subject": "status_on_date", "operator": "IN",
             "comparator": ["Новая", "Открыта", "Просрочена"], "clause": "WHERE", "isExtra": False, "isNew": False,
             "filterOptionName": "filter_open_statuses"}
ISSUE_COLS = ["status_on_date", "issue_key", "rule_code", "object_name", "object_type", "field_name", "actual_value", "expected_value",
              "error", "tobo_name", "responsible_login", "first_seen_date", "due_date", "severity"]

def issues_table(key, name, ds="dq_issues_on_date", extra_filters=None, cols=None, page=10):
    return chart(key, name, "table", ds, {
        "query_mode": "raw", "all_columns": cols or ISSUE_COLS, "groupby": [], "metrics": [],
        "adhoc_filters": [OPEN_ONLY] + (extra_filters or []),
        "order_by_cols": [json.dumps(["due_date", True])], "row_limit": 50000,
        "server_pagination": True, "server_page_length": page, "page_length": page, "include_search": True,
        "allow_rearrange_columns": True, "table_timestamp_format": "%d.%m.%Y",
        "conditional_formatting": [{"column": "status_on_date", "operator": "==", "targetValue": "Просрочена", "colorScheme": "#D92D20"}]})

MEMBER_METRICS = ["open", "overdue", "overdue_pct", "crit", "new_7d", "fixed_7d", "avg_fix_days", "delta_open_7d"]

# ---------------------------------------------------------------- tabs
TABS = []  # (tab_key, title, rows: [[(chart, width, height)]])

# Обзор
bn = [big_number("bn_open", "Открытые ошибки", "open", "за 7 дней"),
      big_number("bn_overdue", "Открытые просроченные", "overdue", "за 7 дней"),
      big_number("bn_pct", "Доля просроченных", "overdue_pct", "за 7 дней", ".1%"),
      big_number("bn_new", "Новые за 7 дней", "new_7d", "за 7 дней"),
      big_number("bn_fixed", "Исправлено за 7 дней", "fixed_7d", "за 7 дней"),
      chart("bn_median", "Медиана исправления, дн.", "big_number_total", "dq_issues_on_date", {
          "metric": "median_fix_days", "subheader": "по исправленным за 30 дней", "y_axis_format": ",d", "header_font_size": 0.4})]
ov_line = open_closed_line("ov_line", "Открытые и закрытые ошибки по дням")
ov_stack = chart("ov_stack", "Открытые ошибки по типу объекта и важности", "echarts_timeseries_bar", "dq_agg_on_date", {
    "x_axis": "object_type", "groupby": ["severity"], "metrics": ["open"], "stack": "Stack", "orientation": "vertical",
    "row_limit": 1000, "show_value": True, "show_legend": True, "legendOrientation": "top", "rich_tooltip": True,
    "x_axis_sort_series": "sum", "x_axis_sort_series_ascending": False, "y_axis_format": ",d"})
TABS.append(("overview", "Обзор", [[(c, 2, 30) for c in bn], [(ov_line, 12, 60)], [(ov_stack, 12, 52)]]))

def dim_tab(tk, title, dimcol, dims_table, one):
    top = hbar(f"{tk}_top", f"Топ-10: {title.lower()} по открытым ошибкам", "dq_agg_on_date", dimcol, ["overdue", "in_time"], "open")
    line = open_closed_line(f"{tk}_line", "Открытые и закрытые ошибки по дням")
    tbl = member_table(f"{tk}_table", title, "dq_agg_on_date", dims_table, MEMBER_METRICS)
    by_rule = hbar(f"{tk}_rules", "Открытые по правилам", "dq_agg_on_date", "rule_name", ["overdue", "in_time"], "open", 8)
    ppl = hbar(f"{tk}_people", "Сотрудники с наибольшим числом ошибок", "dq_person_on_date", "login", ["overdue", "in_time"], "open", 8)
    iss = issues_table(f"{tk}_issues", "Открытые ошибки")
    TABS.append((tk, title, [[(top, 6, 50), (line, 6, 50)], [(tbl, 12, 60)], [(by_rule, 6, 50), (ppl, 6, 50)], [(iss, 12, 70)]]))

dim_tab("branch", "Отделения", "tobo_name", ["tobo_name"], "Отделение")
dim_tab("unit", "Подразделения", "responsible_unit_name", ["responsible_unit_name"], "Подразделение")
dim_tab("domain", "Домены", "domain_name", ["domain_name", "parent_domain_name", "business_owner"], "Домен")
dim_tab("product", "Дата-продукты", "data_product_name", ["data_product_name"], "Дата-продукт")

# Сотрудники
p_top = hbar("person_top", "Топ-10: сотрудники по открытым ошибкам", "dq_person_on_date", "login", ["overdue", "in_time"], "open")
p_br = hbar("person_branch", "Открытые по отделениям", "dq_person_on_date", "tobo_name", ["overdue", "in_time"], "open", 8)
p_tbl = member_table("person_table", "Сотрудники", "dq_person_on_date", ["login", "employee_name", "employee_branch", "employee_status"], MEMBER_METRICS,
                     {"employee_status": {}})
p_rule = hbar("person_rules", "Открытые по правилам", "dq_person_on_date", "rule_name", ["overdue", "in_time"], "open", 8)
p_iss = issues_table("person_issues", "Открытые ошибки сотрудника", "dq_person_on_date",
                     cols=ISSUE_COLS[:-4] + ["role", "login", "first_seen_date", "due_date", "severity"])
TABS.append(("person", "Сотрудники", [[(p_top, 6, 50), (p_br, 6, 50)], [(p_tbl, 12, 60)], [(p_rule, 12, 50)], [(p_iss, 12, 70)]]))

# Правила
r_top = hbar("rule_top", "Топ-10: правила по открытым ошибкам", "dq_agg_on_date", "rule_name", ["overdue", "in_time"], "open")
r_pass = chart("rule_pass", "Процент прохождения правила", "echarts_timeseries_line", "v_rule_pass", {
    "x_axis": "run_date", "time_grain_sqla": "P1D", "metrics": ["pass_rate", "threshold"], "groupby": [],
    "show_legend": True, "legendOrientation": "top", "rich_tooltip": True, "y_axis_format": ".2%",
    "x_axis_time_format": "%d %b", "tooltipTimeFormat": "%d.%m.%Y", "markerEnabled": False},
    desc="Выберите правило кросс-фильтром: 1 − ошибок / проверено записей и порог правила.")
r_tbl = member_table("rule_table", "Правила", "dq_agg_on_date", ["rule_code", "rule_name", "domain_name", "severity"], MEMBER_METRICS)
r_pass_tbl = chart("rule_pass_table", "Прохождение правил и ссылки в UMIDA", "table", "v_rule_pass", {
    "query_mode": "aggregate", "groupby": ["rule_code", "rule_name", "umida_link"],
    "metrics": ["pass_rate_last", "threshold", "failed_last", "total_last"], "order_desc": False,
    "timeseries_limit_metric": "pass_rate_last", "row_limit": 1000, "page_length": 10, "include_search": True,
    "allow_render_html": True, "show_cell_bars": False,
    "conditional_formatting": [{"column": "pass_rate_last", "operator": "<", "targetValue": 0.995, "colorScheme": "#D92D20"}]})
r_br = hbar("rule_branch", "Открытые по отделениям", "dq_agg_on_date", "tobo_name", ["overdue", "in_time"], "open", 8)
r_ppl = hbar("rule_people", "Сотрудники с наибольшим числом ошибок", "dq_person_on_date", "login", ["overdue", "in_time"], "open", 8)
r_iss = issues_table("rule_issues", "Открытые ошибки")
TABS.append(("rule", "Правила", [[(r_top, 6, 50), (r_pass, 6, 50)], [(r_tbl, 12, 60)], [(r_pass_tbl, 12, 50)],
                                 [(r_br, 6, 50), (r_ppl, 6, 50)], [(r_iss, 12, 70)]]))

# Влияние на отчёты
i_bar = hbar("impact_bar", "Отчёты под риском", "dq_report_on_date", "report_name", ["crit", "others"], "open")
i_tbl = chart("impact_table", "Отчёты и сумма под риском", "table", "dq_report_on_date", {
    "query_mode": "aggregate", "groupby": ["report_name", "report_type"], "metrics": ["open", "crit", "overdue", "amount_sum"],
    "timeseries_limit_metric": "crit", "order_desc": True, "row_limit": 1000, "page_length": 10, "include_search": True,
    "show_cell_bars": True, "column_config": {"open": {"showCellBars": True}, "crit": {"showCellBars": False}}})
i_chain = chart("impact_chain", "Цепочки влияния: правило → объект → домен → отчёт", "table", "dq_report_on_date", {
    "query_mode": "aggregate", "groupby": ["rule_code", "rule_name", "object_type", "domain_name", "report_name"],
    "metrics": ["open", "amount_sum"], "timeseries_limit_metric": "open", "order_desc": True, "row_limit": 5000,
    "page_length": 10, "include_search": True, "show_cell_bars": True})
i_iss = chart("impact_issues", "Открытые ошибки по отчётам", "table", "dq_report_on_date", {
    "query_mode": "raw", "all_columns": ["status_on_date", "issue_key", "report_name", "rule_code", "object_name", "object_type", "error",
                                         "amount", "tobo_name", "responsible_login", "due_date", "severity"],
    "order_by_cols": [json.dumps(["due_date", True])], "row_limit": 50000, "server_pagination": True,
    "server_page_length": 10, "page_length": 10, "include_search": True, "table_timestamp_format": "%d.%m.%Y"})
TABS.append(("impact", "Влияние на отчёты", [[(i_bar, 6, 50), (i_tbl, 6, 50)], [(i_chain, 12, 55)], [(i_iss, 12, 70)]]))

# Журнал
JOURNAL_COLS = ["status_on_date", "tobo_name", "source_name", "object_type", "object_id", "object_name", "field_name", "actual_value",
                "expected_value", "error_type", "error", "information", "created_by_login", "executed_by_login", "modified_by_login",
                "manager_login", "responsible_login", "severity", "first_seen_date", "due_date", "closed_date", "exception_reason",
                "rule_code", "domain_name", "data_product_name", "dimension", "responsible_unit_name", "entity_type", "error_code", "issue_key"]
j = chart("journal", "Журнал ошибок", "table", "dq_issues_on_date", {
    "query_mode": "raw", "all_columns": JOURNAL_COLS, "order_by_cols": [json.dumps(["due_date", True])], "row_limit": 100000,
    "server_pagination": True, "server_page_length": 25, "page_length": 25, "include_search": True,
    "allow_rearrange_columns": True, "table_timestamp_format": "%d.%m.%Y",
    "conditional_formatting": [{"column": "status_on_date", "operator": "==", "targetValue": "Просрочена", "colorScheme": "#D92D20"}]},
    desc="Статусы — из фильтра «Статус ошибки». Справа служебные поля журнала.")
TABS.append(("journal", "Журнал ошибок", [[(j, 12, 100)]]))

# ---------------------------------------------------------------- dashboard layout
pos = {"DASHBOARD_VERSION_KEY": "v2",
       "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["TABS-dq"]},
       "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": "DQ Монитор ошибок"}},
       "TABS-dq": {"id": "TABS-dq", "type": "TABS", "children": [], "parents": ["ROOT_ID"], "meta": {}}}
TAB_OF_CHART = {}
for tk, title, rows in TABS:
    tid = f"TAB-{tk}"
    pos["TABS-dq"]["children"].append(tid)
    pos[tid] = {"id": tid, "type": "TAB", "children": [], "parents": ["ROOT_ID", "TABS-dq"],
                "meta": {"text": title, "defaultText": "Tab title", "placeholder": "Tab title"}}
    for ri, row in enumerate(rows):
        rid = f"ROW-{tk}-{ri}"
        pos[tid]["children"].append(rid)
        pos[rid] = {"id": rid, "type": "ROW", "children": [], "parents": ["ROOT_ID", "TABS-dq", tid],
                    "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        for c, w, h in row:
            cid = f"CHART-{c['key']}"
            pos[rid]["children"].append(cid)
            pos[cid] = {"id": cid, "type": "CHART", "children": [], "parents": ["ROOT_ID", "TABS-dq", tid, rid],
                        "meta": {"chartId": c["id"], "width": w, "height": h, "uuid": c["uuid"], "sliceName": c["slice_name"]}}
            TAB_OF_CHART[c["id"]] = tid

ALL = [c["id"] for c in CHARTS]
by_ds = lambda ds: [c["id"] for c in CHARTS if c["ds"] == ds]
TAB_IDS = [f"TAB-{t[0]}" for t in TABS]

def sel_filter(fid, name, ds, column, multi=True, default=None, required=False, scope_ids=None, desc="", parents=None, search=False):
    in_scope = scope_ids if scope_ids is not None else ALL
    dm = {"extraFormData": {}, "filterState": {}, "ownState": {}}
    if default:
        dm = {"extraFormData": {"filters": [{"col": column, "op": "IN", "val": default}]},
              "filterState": {"value": default, "label": ", ".join(default)}, "ownState": {}}
    return {"id": fid, "name": name, "filterType": "filter_select", "type": "NATIVE_FILTER", "description": desc,
            "targets": [{"datasetUuid": DSU[ds], "column": {"name": column}}],
            "controlValues": {"enableEmptyFilter": required, "defaultToFirstItem": False, "multiSelect": multi,
                              "searchAllOptions": search, "inverseSelection": False, "creatable": False},
            "defaultDataMask": dm, "cascadeParentIds": parents or [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": [i for i in ALL if i not in in_scope]},
            "chartsInScope": in_scope, "tabsInScope": sorted({TAB_OF_CHART[i] for i in in_scope})}

native_filters = [
    {"id": "NATIVE_FILTER-period", "name": "Период", "filterType": "filter_time", "type": "NATIVE_FILTER",
     "description": "Дата отчёта = последний день периода. Линейные графики показывают весь период.",
     "targets": [{}], "controlValues": {"enableEmptyFilter": True},
     "defaultDataMask": {"extraFormData": {"time_range": "90 days ago : tomorrow"}, "filterState": {"value": "90 days ago : tomorrow"}, "ownState": {}},
     "cascadeParentIds": [], "scope": {"rootPath": ["ROOT_ID"], "excluded": []}, "chartsInScope": ALL, "tabsInScope": TAB_IDS},
    sel_filter("NATIVE_FILTER-severity", "Важность", "dq_agg_on_date", "severity"),
    sel_filter("NATIVE_FILTER-object", "Тип объекта", "dq_agg_on_date", "object_type"),
    sel_filter("NATIVE_FILTER-source", "Система-источник", "dq_agg_on_date", "source_name"),
    sel_filter("NATIVE_FILTER-branch", "Отделение", "dq_agg_on_date", "tobo_name", search=True),
    sel_filter("NATIVE_FILTER-pdomain", "Родительский домен", "dq_agg_on_date", "parent_domain_name"),
    sel_filter("NATIVE_FILTER-domain", "Домен", "dq_agg_on_date", "domain_name", parents=["NATIVE_FILTER-pdomain"]),
    sel_filter("NATIVE_FILTER-status", "Статус ошибки", "dq_issues_on_date", "status_on_date",
               default=["Новая", "Открыта", "Просрочена"], scope_ids=[j["id"]], desc="Только для вкладки «Журнал ошибок»."),
    sel_filter("NATIVE_FILTER-role", "Роль сотрудника", "dq_person_on_date", "role", multi=False, required=True,
               default=["Ответственный"], scope_ids=by_ds("dq_person_on_date"),
               desc="В какой роли считать ошибки сотрудника: ответственный, создал, провёл, изменил, менеджер."),
]

LABEL_COLORS = {
    "Открытые": "#1A1A1A", "Открытые просроченные": "#D92D20", "Открытые в срок": "#FFCC00", "Закрытые": "#12A150",
    "Закрытые с просрочкой": "#E08A00", "Критический": "#D92D20", "Высокий": "#F08A80", "Средний": "#FFCC00",
    "Низкий": "#BFBFBF", "Критичные": "#D92D20", "Остальные": "#FFCC00", "Процент прохождения": "#1A1A1A", "Порог правила": "#D92D20",
}
metadata = {
    "color_scheme": "kapitalbank", "label_colors": LABEL_COLORS, "shared_label_colors": [], "color_scheme_domain": [],
    "cross_filters_enabled": True, "native_filter_configuration": native_filters,
    "chart_configuration": {str(i): {"id": i, "crossFilters": {"scope": "global", "chartsInScope": [x for x in ALL if x != i]}} for i in ALL},
    "global_chart_configuration": {"scope": {"rootPath": ["ROOT_ID"], "excluded": []}, "chartsInScope": ALL},
    "refresh_frequency": 0, "expanded_slices": {}, "timed_refresh_immune_slices": [], "default_filters": "{}", "filter_scopes": {},
}
CSS = """
.dashboard-header .header-with-actions { border-bottom: 4px solid #FFCC00; }
.dashboard-component-chart-holder { border-radius: 8px; }
"""
dashboard = {
    "dashboard_title": "DQ Монитор ошибок", "description": None, "css": CSS, "slug": "dq-monitor",
    "certified_by": "Data Office", "certification_details": "Витрины dq.* на StarRocks, правила UMIDA",
    "published": True, "uuid": U("dashboard:dq-monitor"), "position": pos, "metadata": metadata, "version": "1.0.0",
}

# ---------------------------------------------------------------- write zip
def dump(o):
    return yaml.safe_dump(o, allow_unicode=True, sort_keys=False, width=1000)

def safe(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s)[:60]

OUT.mkdir(parents=True, exist_ok=True)
zpath = OUT / "dq_monitor_dashboard.zip"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(f"{ROOT}/metadata.yaml", dump({"version": "1.0.0", "type": "Dashboard",
                                              "timestamp": datetime.now(timezone.utc).isoformat()}))
    z.writestr(f"{ROOT}/databases/dwhstarrocks.yaml", dump(database))
    for d in DATASETS:
        z.writestr(f"{ROOT}/datasets/dwhstarrocks/{d['table_name']}.yaml", dump(d))
    for c in CHARTS:
        out = {k: v for k, v in c.items() if k not in ("key", "id", "ds")}
        z.writestr(f"{ROOT}/charts/{c['key']}_{c['id']}.yaml", dump(out))
    z.writestr(f"{ROOT}/dashboards/DQ_monitor.yaml", dump(dashboard))

print(f"{zpath}: {len(DATASETS)} datasets, {len(CHARTS)} charts, {len(TABS)} tabs, {len(native_filters)} native filters")
