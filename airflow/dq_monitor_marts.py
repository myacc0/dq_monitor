"""
DQ Монитор ошибок — обновление витрин для Superset.

Порядок: ждём завершения ночного прогона правил UMIDA → реестр ошибок → дневной агрегат →
прогрев кэша дашборда (необязательно).

Подключение `starrocks_dwh` — MySQL-протокол StarRocks (FE, порт 9030).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.providers.common.sql.sensors.sql import SqlSensor
from airflow.sdk import DAG

SQL_DIR = Path(__file__).parent / "sql"
CONN_ID = "starrocks_dwh"

default_args = {
    "owner": "data-office-de",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="dq_monitor_marts",
    description="Витрины DQ Монитора ошибок: реестр ошибок и дневной агрегат",
    schedule="30 5 * * *",            # 05:30 Asia/Tashkent, после ночных проверок UMIDA
    start_date=datetime(2026, 11, 1),
    catchup=False,
    default_args=default_args,
    tags=["data-quality", "umida", "superset"],
) as dag:

    # Все правила, запланированные на сегодня, отработали (нет запусков в статусе Running)
    wait_umida_runs = SqlSensor(
        task_id="wait_umida_runs",
        conn_id=CONN_ID,
        sql="""
            select count(*) = 0
            from umida.dq_rule_run
            where date(started_at) = current_date()
              and status in ('Running', 'Queued')
        """,
        poke_interval=300,
        timeout=3 * 60 * 60,
        mode="reschedule",
    )

    build_registry = SQLExecuteQueryOperator(
        task_id="build_issue_registry",
        conn_id=CONN_ID,
        sql=(SQL_DIR / "02_issue_registry.sql").read_text(encoding="utf-8"),
    )

    build_daily = SQLExecuteQueryOperator(
        task_id="build_agg_issue_daily",
        conn_id=CONN_ID,
        sql=(SQL_DIR / "03_agg_issue_daily.sql").read_text(encoding="utf-8"),
    )

    # Сверка: число открытых ошибок на сегодня в агрегате = в реестре
    check_totals = SqlSensor(
        task_id="check_totals",
        conn_id=CONN_ID,
        sql="""
            select (select sum(open_cnt) from dq.agg_issue_daily where report_date = current_date())
                 = (select count(*) from dq.issue_registry
                    where first_seen_date <= current_date()
                      and (closed_date is null or closed_date > current_date()))
        """,
        poke_interval=60,
        timeout=600,
        mode="poke",
    )

    wait_umida_runs >> build_registry >> build_daily >> check_totals
