-- =====================================================================
-- DQ Монитор ошибок — DDL витрин (StarRocks 3.x)
-- Источник: dq.issue_journal (создан командой, 42 колонки)
-- Таблицы UMIDA (umida.*) и DWH (dds.*) — см. README, раздел «Маппинг таблиц».
-- =====================================================================

create database if not exists dq;

-- 1. Реестр ошибок: одна строка на ошибку (issue_key), жизненный цикл
create table if not exists dq.issue_registry (
    issue_key              varchar(32)    not null comment 'md5(rule_id|entity_gid|error_code)',
    rule_id                varchar(36)    comment 'UUID правила UMIDA',
    rule_code              varchar(20),
    rule_name              varchar(500),
    domain_id              int,
    domain_name            varchar(255),
    parent_domain_name     varchar(255),
    business_owner         varchar(255),
    stewards               varchar(1000),
    data_product_id        int,
    data_product_name      varchar(255),
    responsible_unit_id    varchar(36),
    responsible_unit_name  varchar(500),
    dimension              varchar(50),
    severity               varchar(20),
    fix_days               int,
    tobo_id                varchar(20),
    tobo_name              varchar(255),
    source_code            varchar(20),
    source_name            varchar(100),
    object_type            varchar(50),
    object_id              varchar(100),
    object_name            varchar(1000),
    field_name             varchar(200),
    actual_value           varchar(2000),
    expected_value         varchar(2000),
    error_type             varchar(100),
    error                  varchar(4000),
    information            varchar(4000),
    created_by_login       varchar(100),
    executed_by_login      varchar(100),
    modified_by_login      varchar(100),
    manager_login          varchar(100),
    responsible_login      varchar(100)   comment 'провёл (TRANSACTION/OPERATION), иначе изменил, иначе создал',
    entity_type            varchar(20),
    entity_gid             varchar(50),
    client_gid             varchar(50),
    account_gid            varchar(50),
    contract_gid           varchar(50),
    trx_gid                varchar(50),
    error_code             varchar(50),
    amount                 decimal(20,2)  comment 'сумма объекта из attrs.amount, сум',
    first_seen_date        date,
    last_seen_date         date,
    due_date               date,
    closed_date            date,
    status                 varchar(20)    comment 'текущий статус: Новая/Открыта/Просрочена/Исправлена/Исключение',
    fix_days_actual        int            comment 'closed_date - first_seen_date для исправленных',
    exception_reason       varchar(2000),
    exception_by           varchar(100)
)
primary key (issue_key)
distributed by hash(issue_key) buckets 8
properties ("replication_num" = "3");

-- 2. Дневной агрегат: дата × отделение × правило × ответственный
create table if not exists dq.agg_issue_daily (
    report_date            date           not null,
    tobo_id                varchar(20),
    tobo_name              varchar(255),
    rule_code              varchar(20),
    rule_name              varchar(500),
    domain_name            varchar(255),
    parent_domain_name     varchar(255),
    business_owner         varchar(255),
    data_product_name      varchar(255),
    responsible_unit_name  varchar(500),
    entity_type            varchar(20),
    object_type            varchar(50),
    source_name            varchar(100),
    severity               varchar(20),
    responsible_login      varchar(100),
    open_cnt               bigint  comment 'открыто на дату',
    open_overdue_cnt       bigint  comment 'открыто и просрочено на дату',
    new_cnt                bigint  comment 'обнаружено в этот день',
    closed_cnt             bigint  comment 'закрыто в этот день (исправлено + исключения)',
    closed_late_cnt        bigint  comment 'закрыто в этот день после срока',
    fixed_cnt              bigint  comment 'исправлено в этот день (без исключений)',
    new_7d_cnt             bigint  comment 'обнаружено за 7 дней до даты включительно',
    fixed_7d_cnt           bigint  comment 'исправлено за 7 дней',
    exception_7d_cnt       bigint  comment 'в исключения за 7 дней',
    open_7d_ago_cnt        bigint  comment 'открыто на дату − 7',
    overdue_7d_ago_cnt     bigint  comment 'просрочено на дату − 7',
    fixed_30d_cnt          bigint  comment 'исправлено за 30 дней',
    fix_days_30d_sum       bigint  comment 'сумма дней исправления за 30 дней',
    open_amount            decimal(24,2) comment 'сумма объектов с открытыми ошибками, сум'
)
duplicate key (report_date, tobo_id, rule_code)
partition by date_trunc('month', report_date)
distributed by hash(tobo_id, rule_code) buckets 8
properties ("replication_num" = "3", "partition_live_number" = "13");

-- 3. Справочник зависимостей «правило / домен → отчёт»
create table if not exists dq.report_dependency (
    report_id     varchar(50)   not null,
    report_name   varchar(500),
    report_type   varchar(20)   comment 'Регуляторный / Управленческий',
    rule_code     varchar(20)   comment 'заполняется, если зависимость на уровне правила',
    domain_id     int           comment 'или на уровне домена (с дочерними)'
)
duplicate key (report_id)
distributed by hash(report_id) buckets 1
properties ("replication_num" = "3");

-- 4. Ошибка × роль сотрудника
create or replace view dq.v_issue_person as
select issue_key, 'Ответственный' as role, responsible_login as login from dq.issue_registry where responsible_login is not null
union all select issue_key, 'Создал',   created_by_login  from dq.issue_registry where created_by_login  is not null
union all select issue_key, 'Провёл',   executed_by_login from dq.issue_registry where executed_by_login is not null
union all select issue_key, 'Изменил',  modified_by_login from dq.issue_registry where modified_by_login is not null
union all select issue_key, 'Менеджер', manager_login     from dq.issue_registry where manager_login     is not null;

-- 5. Процент прохождения правил по запускам
create or replace view dq.v_rule_pass as
select rl.code                                             as rule_code,
       rl.name                                             as rule_name,
       rl.id                                               as rule_id,
       concat('<a href="https://umida.kapitalbank.uz/dq-rules/custom-sql/', rl.id,
              '" target="_blank">Открыть ↗</a>')            as umida_link,
       r.id                                                as run_id,
       date(r.started_at)                                  as run_date,
       r.total_records,
       r.failed_records,
       1 - r.failed_records / nullif(r.total_records, 0)   as pass_rate,
       rl.threshold_pct / 100                              as threshold
from umida.dq_rule_run r
join umida.dq_rule rl on rl.id = r.rule_id
where r.status = 'Success';

-- 6. Ошибка × отчёт (по правилу или по домену/родительскому домену)
create or replace view dq.v_issue_report as
with dep as (
    -- зависимость на уровне правила
    select r.issue_key, d.report_id, d.report_name, d.report_type
    from dq.issue_registry r
    join dq.report_dependency d on d.rule_code = r.rule_code
    union
    -- зависимость на уровне домена
    select r.issue_key, d.report_id, d.report_name, d.report_type
    from dq.issue_registry r
    join dq.report_dependency d on d.rule_code is null and d.domain_id = r.domain_id
    union
    -- зависимость на уровне родительского домена
    select r.issue_key, d.report_id, d.report_name, d.report_type
    from dq.issue_registry r
    join umida.dict_data_domain dd on dd.id = r.domain_id
    join dq.report_dependency d on d.rule_code is null and d.domain_id = dd.parent_id
)
select r.*, dep.report_id, dep.report_name, dep.report_type
from dq.issue_registry r
join dep on dep.issue_key = r.issue_key;
