"""
Привязать пакет к уже существующему подключению StarRocks в Superset.

1. Экспортируйте из Superset любой датасет на этом подключении (Датасеты → ⋮ → Экспорт).
2. Посмотрите в архиве databases/<имя>.yaml поле uuid.
3. python set_database_uuid.py <uuid> [dq_monitor_dashboard.zip]
   → dq_monitor_dashboard_<uuid8>.zip — его и импортируйте. Superset возьмёт существующее
     подключение, пароль вводить не придётся.
"""
import sys
import zipfile
from pathlib import Path

import yaml

new_uuid = sys.argv[1]
src = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).with_name("dq_monitor_dashboard.zip"))
dst = src.with_name(f"{src.stem}_{new_uuid[:8]}.zip")

with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
    for name in zin.namelist():
        data = yaml.safe_load(zin.read(name))
        if "/databases/" in name:
            data["uuid"] = new_uuid
        elif "/datasets/" in name:
            data["database_uuid"] = new_uuid
        zout.writestr(name, yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000))
print(dst)
