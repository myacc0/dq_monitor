-- =====================================================================
-- Пересборка реестра ошибок dq.issue_registry из журнала dq.issue_journal.
-- Запускается после каждого прогона правил UMIDA (Airflow, задача build_registry).
-- Ошибка открыта с первого запуска, где найдена; закрыта в первом успешном
-- запуске того же правила, где её уже нет; исключение из UMIDA закрывает датой решения.
-- =====================================================================
insert overwrite dq.issue_registry
with j as (
    select md5(concat_ws('|', rule_id, entity_gid, error_code)) as issue_key, j.*
    from dq.issue_journal j
),
first_last as (
    select issue_key, rule_id,
           min(check_date) as first_seen_date,
           max(check_date) as last_seen_date
    from j
    group by issue_key, rule_id
),
runs as (
    select rule_id, date(started_at) as run_date
    from umida.dq_rule_run
    where status = 'Success'
),
closed as (
    select f.issue_key, min(r.run_date) as closed_date
    from first_last f
    join runs r on r.rule_id = f.rule_id and r.run_date > f.last_seen_date
    group by f.issue_key
),
last_row as (
    select * from (
        select j.*, row_number() over (partition by issue_key order by check_date desc, run_id desc) as rn
        from j
    ) t
    where rn = 1
),
dom as (
    select d.id, d.short_name as domain_name, p.short_name as parent_domain_name,
           d.business_owner_name as business_owner,
           (select group_concat(s.full_name separator ', ') from umida.dict_data_domain_steward s where s.domain_id = d.id) as stewards
    from umida.dict_data_domain d
    left join umida.dict_data_domain p on p.id = d.parent_id
),
base as (
    select
        l.issue_key, l.rule_id, l.rule_code, rl.name as rule_name,
        l.domain_id, dom.domain_name, dom.parent_domain_name, dom.business_owner, dom.stewards,
        l.data_product_id, dp.name as data_product_name,
        l.responsible_unit_id, ou.name as responsible_unit_name,
        l.dimension, l.severity, l.fix_days,
        l.tobo_id, l.tobo_name, l.source_code, l.source_name,
        l.object_type, l.object_id, l.object_name, l.field_name,
        l.actual_value, l.expected_value, l.error_type, l.error, l.information,
        l.created_by_login, l.executed_by_login, l.modified_by_login, l.manager_login,
        case when l.entity_type in ('TRANSACTION', 'OPERATION') then l.executed_by_login
             else coalesce(l.modified_by_login, l.created_by_login) end         as responsible_login,
        l.entity_type, l.entity_gid, l.client_gid, l.account_gid, l.contract_gid, l.trx_gid, l.error_code,
        cast(get_json_double(l.attrs, '$.amount') as decimal(20,2))            as amount,
        f.first_seen_date, f.last_seen_date,
        date_add(f.first_seen_date, l.fix_days)                                as due_date,
        coalesce(date(e.decided_at), c.closed_date)                            as closed_date,
        e.issue_key is not null                                                as is_exception,
        e.reason      as exception_reason,
        e.decided_by  as exception_by
    from last_row l
    join first_last f            on f.issue_key = l.issue_key
    left join closed c           on c.issue_key = l.issue_key
    left join umida.dq_issue_exception e on e.issue_key = l.issue_key
    left join umida.dq_rule rl   on rl.id = l.rule_id
    left join dom                on dom.id = l.domain_id
    left join umida.dict_data_product dp on dp.id = l.data_product_id
    left join umida.org_unit ou  on ou.id = l.responsible_unit_id
)
select
    issue_key, rule_id, rule_code, rule_name, domain_id, domain_name, parent_domain_name, business_owner, stewards,
    data_product_id, data_product_name, responsible_unit_id, responsible_unit_name, dimension, severity, fix_days,
    tobo_id, tobo_name, source_code, source_name, object_type, object_id, object_name, field_name,
    actual_value, expected_value, error_type, error, information,
    created_by_login, executed_by_login, modified_by_login, manager_login, responsible_login,
    entity_type, entity_gid, client_gid, account_gid, contract_gid, trx_gid, error_code, amount,
    first_seen_date, last_seen_date, due_date, closed_date,
    case when is_exception                                   then 'Исключение'
         when closed_date is not null                        then 'Исправлена'
         when current_date() > due_date                      then 'Просрочена'
         when datediff(current_date(), first_seen_date) <= 1 then 'Новая'
         else 'Открыта' end                                                    as status,
    case when closed_date is not null and not is_exception
         then datediff(closed_date, first_seen_date) end                       as fix_days_actual,
    exception_reason, exception_by
from base;
