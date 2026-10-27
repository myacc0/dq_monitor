"""Структурная проверка пакета: ссылки на датасеты, метрики, колонки, позиции и фильтры."""
import json, sys, zipfile, yaml
z = zipfile.ZipFile(sys.argv[1] if len(sys.argv) > 1 else "superset/dq_monitor_dashboard.zip")
files = {n: yaml.safe_load(z.read(n)) for n in z.namelist()}
dbs = {v["uuid"] for k, v in files.items() if "/databases/" in k}
ds = {v["uuid"]: v for k, v in files.items() if "/datasets/" in k}
charts = {v["uuid"]: v for k, v in files.items() if "/charts/" in k}
dash = next(v for k, v in files.items() if "/dashboards/" in k)
err = []
for d in ds.values():
    if d["database_uuid"] not in dbs: err.append(f"dataset {d['table_name']}: database not found")
for c in charts.values():
    d = ds.get(c["dataset_uuid"])
    if not d: err.append(f"chart {c['slice_name']}: dataset missing"); continue
    mnames = {m["metric_name"] for m in d["metrics"]}; cnames = {x["column_name"] for x in d["columns"]}
    p = c["params"]
    for key in ("metrics", "metrics_b"):
        for m in p.get(key, []) or []:
            if m not in mnames: err.append(f"{c['slice_name']}: metric {m} not in {d['table_name']}")
    for key in ("metric", "timeseries_limit_metric"):
        if p.get(key) and p[key] not in mnames: err.append(f"{c['slice_name']}: {key} {p[key]} not in {d['table_name']}")
    for key in ("groupby", "groupby_b", "all_columns"):
        for g in p.get(key, []) or []:
            if g not in cnames: err.append(f"{c['slice_name']}: column {g} not in {d['table_name']}")
    if p.get("x_axis") and p["x_axis"] not in cnames: err.append(f"{c['slice_name']}: x_axis {p['x_axis']} missing")
    for f in p.get("adhoc_filters", []):
        if f["subject"] not in cnames: err.append(f"{c['slice_name']}: filter col {f['subject']} missing")
    for oc in p.get("order_by_cols", []):
        if json.loads(oc)[0] not in cnames: err.append(f"{c['slice_name']}: order col missing")
pos = dash["position"]
chart_uuids_in_pos = {v["meta"]["uuid"] for k, v in pos.items() if isinstance(v, dict) and v.get("type") == "CHART"}
ids_in_pos = {v["meta"]["chartId"] for k, v in pos.items() if isinstance(v, dict) and v.get("type") == "CHART"}
if chart_uuids_in_pos != set(charts): err.append("position/chart uuid mismatch")
for k, v in pos.items():
    if not isinstance(v, dict): continue
    for ch in v.get("children", []):
        if ch not in pos: err.append(f"position child {ch} missing")
for f in dash["metadata"]["native_filter_configuration"]:
    for t in f["targets"]:
        if t and t["datasetUuid"] not in ds: err.append(f"filter {f['name']}: dataset missing")
        if t and t["column"]["name"] not in {x["column_name"] for x in ds[t["datasetUuid"]]["columns"]}: err.append(f"filter {f['name']}: column missing")
    if not set(f["chartsInScope"]) <= ids_in_pos: err.append(f"filter {f['name']}: scope ids unknown")
for k in dash["metadata"]["chart_configuration"]:
    if int(k) not in ids_in_pos: err.append("chart_configuration id unknown")
print("OK" if not err else "\n".join(err))
print(f"datasets={len(ds)} charts={len(charts)} filters={len(dash['metadata']['native_filter_configuration'])}")
