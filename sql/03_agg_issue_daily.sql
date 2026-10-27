-- =====================================================================
-- Дневной агрегат dq.agg_issue_daily за последние 13 месяцев.
-- Строка = дата × отделение × правило × ответственный × важность × тип объекта.
-- В соединение попадают ошибки, открытые на дату или закрытые за 30 дней до неё,
-- чтобы корректно посчитать 7- и 30-дневные показатели.
-- =====================================================================
insert overwrite dq.agg_issue_daily
select
    c.dt                                                   as report_date,
    r.tobo_id, r.tobo_name, r.rule_code, r.rule_name,
    r.domain_name, r.parent_domain_name, r.business_owner, r.data_product_name, r.responsible_unit_name,
    r.entity_type, r.object_type, r.source_name, r.severity, r.responsible_login,

    count(case when r.first_seen_date <= c.dt and (r.closed_date is null or r.closed_date > c.dt) then 1 end)            as open_cnt,
    count(case when r.first_seen_date <= c.dt and (r.closed_date is null or r.closed_date > c.dt)
                and c.dt > r.due_date then 1 end)                                                                       as open_overdue_cnt,
    count(case when r.first_seen_date = c.dt then 1 end)                                                                as new_cnt,
    count(case when r.closed_date = c.dt then 1 end)                                                                    as closed_cnt,
    count(case when r.closed_date = c.dt and r.closed_date > r.due_date then 1 end)                                     as closed_late_cnt,
    count(case when r.closed_date = c.dt and r.status = 'Исправлена' then 1 end)                                        as fixed_cnt,
    count(case when r.first_seen_date between date_sub(c.dt, 6) and c.dt then 1 end)                                   as new_7d_cnt,
    count(case when r.closed_date between date_sub(c.dt, 6) and c.dt and r.status = 'Исправлена' then 1 end)           as fixed_7d_cnt,
    count(case when r.closed_date between date_sub(c.dt, 6) and c.dt and r.status = 'Исключение' then 1 end)           as exception_7d_cnt,
    count(case when r.first_seen_date <= date_sub(c.dt, 7)
                and (r.closed_date is null or r.closed_date > date_sub(c.dt, 7)) then 1 end)                           as open_7d_ago_cnt,
    count(case when r.first_seen_date <= date_sub(c.dt, 7)
                and (r.closed_date is null or r.closed_date > date_sub(c.dt, 7))
                and date_sub(c.dt, 7) > r.due_date then 1 end)                                                          as overdue_7d_ago_cnt,
    count(case when r.closed_date between date_sub(c.dt, 29) and c.dt and r.status = 'Исправлена' then 1 end)          as fixed_30d_cnt,
    sum(case when r.closed_date between date_sub(c.dt, 29) and c.dt and r.status = 'Исправлена'
             then r.fix_days_actual else 0 end)                                                                        as fix_days_30d_sum,
    sum(case when r.first_seen_date <= c.dt and (r.closed_date is null or r.closed_date > c.dt)
             then coalesce(r.amount, 0) else 0 end)                                                                    as open_amount
from dds.dim_calendar c
join dq.issue_registry r
  on r.first_seen_date <= c.dt
 and (r.closed_date is null or r.closed_date >= date_sub(c.dt, 29))
where c.dt between date_sub(current_date(), 395) and current_date()
group by c.dt, r.tobo_id, r.tobo_name, r.rule_code, r.rule_name,
         r.domain_name, r.parent_domain_name, r.business_owner, r.data_product_name, r.responsible_unit_name,
         r.entity_type, r.object_type, r.source_name, r.severity, r.responsible_login;
