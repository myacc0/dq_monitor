# =====================================================================
# Фрагмент superset_config.py для дашборда «DQ Монитор ошибок».
# Добавить в ваш superset_config.py (не заменять его целиком) и перезапустить Superset.
# Ключи темы проверены по схеме Superset 6 (Ant Design 5); при отличиях в 7-й версии
# сверьте названия в документации вашей сборки.
# =====================================================================

FEATURE_FLAGS = {
    **globals().get("FEATURE_FLAGS", {}),
    "ENABLE_TEMPLATE_PROCESSING": True,   # Jinja в виртуальных датасетах (get_time_filter)
    "DASHBOARD_CROSS_FILTERS": True,      # кросс-фильтры
    "DASHBOARD_RBAC": True,               # доступ к дашборду по ролям
    "DRILL_TO_DETAIL": True,
}

# Категориальная схема Kapitalbank — её использует дашборд (color_scheme = "kapitalbank")
EXTRA_CATEGORICAL_COLOR_SCHEMES = [
    {
        "id": "kapitalbank",
        "description": "Kapitalbank: открытые, просроченные, в срок, закрытые",
        "label": "Kapitalbank",
        "isDefault": False,
        "colors": ["#1A1A1A", "#FFCC00", "#D92D20", "#12A150", "#E08A00", "#8C8C8C", "#F08A80", "#1677FF"],
    }
]

# Тема Kapitalbank (Superset 6+ theming)
THEME_DEFAULT = {
    "token": {
        "colorPrimary": "#FFCC00",
        "colorTextLightSolid": "#1A1A1A",   # текст на жёлтых кнопках — чёрный
        "colorLink": "#1677FF",
        "colorError": "#D92D20",
        "colorSuccess": "#12A150",
        "colorWarning": "#E08A00",
        "borderRadius": 6,
        "fontFamily": "Inter, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
        "brandLogoUrl": "/static/assets/images/kapitalbank_logo.svg",   # положить файл логотипа
        "brandLogoAlt": "Kapitalbank",
        "brandLogoHref": "/superset/welcome/",
    },
    "algorithm": "default",
}

# Время выполнения тяжёлых таблиц (журнал)
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 120
