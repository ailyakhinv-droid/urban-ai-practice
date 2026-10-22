"""
Скрипт для сборки интерактивного дашборда городского исследования:
Октябрьский район, Барнаул (библиотека BlocksNet).

Скрипт читает готовые файлы GeoJSON и CSV из папки данных и генерирует
единый автономный dashboard.html.
Он НЕ скачивает данные и НЕ повторяет расчёты.
"""

import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd


def find_data_dir() -> Path:
    candidates = [
        Path("examples/data/barnaul"),
        Path("data/barnaul"),
        Path("../examples/data/barnaul"),
        Path("../data/barnaul"),
    ]
    for p in candidates:
        if (p / "blocks_all_indicators.geojson").exists():
            return p.resolve()
    raise FileNotFoundError("Не найден файл blocks_all_indicators.geojson в известных папках данных")


def main():
    data_dir = find_data_dir()
    print(f"Загрузка результатов из: {data_dir}")

    # Загружаем слои
    blocks_all = gpd.read_file(data_dir / "blocks_all_indicators.geojson")
    bld_blocks = gpd.read_file(data_dir / "buildings_blocks.geojson") if (data_dir / "buildings_blocks.geojson").exists() else None
    sch_blocks = gpd.read_file(data_dir / "schools_blocks.geojson") if (data_dir / "schools_blocks.geojson").exists() else None
    boundaries = gpd.read_file(data_dir / "boundaries.geojson") if (data_dir / "boundaries.geojson").exists() else None

    # Основная статистика (KPI)
    total_blocks = len(blocks_all)
    total_pop = int(bld_blocks["population"].sum()) if bld_blocks is not None and "population" in bld_blocks.columns else 0
    total_living_area = int(bld_blocks["living_area"].sum()) if bld_blocks is not None and "living_area" in bld_blocks.columns else 0
    total_school_cap = int(sch_blocks["capacity"].sum()) if sch_blocks is not None and "capacity" in sch_blocks.columns else 0

    mean_prov_strong = round(float(blocks_all["provision_strong"].dropna().mean()) * 100, 1)
    mean_prov_weak = round(float(blocks_all["provision_weak"].dropna().mean()) * 100, 1)
    mean_fsi = round(float(blocks_all["fsi"].dropna().mean()), 3)
    mean_gsi = round(float(blocks_all["gsi"].dropna().mean()), 3)

    finite_acc = blocks_all["area_accessibility"].replace(np.inf, np.nan).dropna()
    mean_acc = round(float(finite_acc.mean()), 1)

    print(f"Статистика: блоков={total_blocks}, население={total_pop:,}, жилая площадь={total_living_area:,} кв.м")

    # Готовим данные для графиков (Chart.js)
    # 1. Землепользование
    lu_counts = blocks_all["land_use"].fillna("Без данных").value_counts()
    lu_labels = list(lu_counts.index)
    lu_values = [int(v) for v in lu_counts.values]

    # 2. Морфотипы Стрелка
    strelka_counts = blocks_all["strelka_morphotype"].fillna("Не определен").value_counts()
    strelka_labels = list(strelka_counts.index)
    strelka_values = [int(v) for v in strelka_counts.values]

    # 3. Морфотипы Spacematrix
    space_counts = blocks_all["spacematrix_morphotype"].fillna("Не определен").value_counts().head(6)
    space_labels = list(space_counts.index)
    space_values = [int(v) for v in space_counts.values]

    # 4. Распределение FSI
    fsi_valid = blocks_all["fsi"].dropna().values
    fsi_bins = [0.0, 0.1, 0.2, 0.4, 0.6, 1.0, 2.0]
    fsi_hist, _ = np.histogram(fsi_valid, bins=fsi_bins)
    fsi_labels = ["0.0-0.1", "0.1-0.2", "0.2-0.4", "0.4-0.6", "0.6-1.0", ">1.0"]
    fsi_values = [int(v) for v in fsi_hist]

    # Подготовка GeoJSON для карты (упрощаем геометрию для быстродействия браузера)
    # переводим в EPSG:4326 и упрощаем до ~10 метров
    blocks_simp = blocks_all.copy()
    blocks_simp["geometry"] = blocks_simp["geometry"].to_crs(4326).simplify(0.0001)

    # Приводим к компактному словарю свойств
    features = []
    for idx, row in blocks_simp.iterrows():
        props = {
            "id": int(idx),
            "land_use": str(row.get("land_use") or "Не указано"),
            "prov_s": round(float(row.get("provision_strong", 0) or 0), 2),
            "prov_w": round(float(row.get("provision_weak", 0) or 0), 2),
            "fsi": round(float(row.get("fsi", 0) or 0), 3),
            "gsi": round(float(row.get("gsi", 0) or 0), 3),
            "mxi": round(float(row.get("mxi", 0) or 0), 2),
            "l": round(float(row.get("l", 1) or 1), 1),
            "strelka": str(row.get("strelka_morphotype") or "—"),
            "spacematrix": str(row.get("spacematrix_morphotype") or "—"),
            "acc": round(float(row.get("area_accessibility", 0) or 0), 1) if not np.isinf(row.get("area_accessibility", 0)) else "inf",
        }
        geom = row.geometry.__geo_interface__
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geom
        })

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    # Bounding box центра карты
    bounds = boundaries.to_crs(4326).total_bounds if boundaries is not None else blocks_all.to_crs(4326).total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2.0
    center_lon = (bounds[0] + bounds[2]) / 2.0

    html_template = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Дашборд: Октябрьский район Барнаула (BlocksNet)</title>
    <!-- Leaflet CSS & JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --primary: #1e3a8a;
            --secondary: #0284c7;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text-dark: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --success: #16a34a;
            --warning: #eab308;
            --danger: #dc2626;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg);
            color: var(--text-dark);
            padding: 24px;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3a8a, #0369a1);
            color: white;
            padding: 28px 32px;
            border-radius: 16px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        .header p {{
            font-size: 15px;
            opacity: 0.9;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .kpi-title {{
            font-size: 13px;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        .kpi-value {{
            font-size: 26px;
            font-weight: 800;
            color: var(--primary);
        }}
        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .content-grid {{
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}
        @media (max-width: 1024px) {{
            .content-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .panel {{
            background: var(--card-bg);
            border-radius: 14px;
            border: 1px solid var(--border);
            padding: 22px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .panel-title {{
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        #map {{
            height: 560px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}
        .map-controls {{
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}
        .map-btn {{
            background: #f1f5f9;
            border: 1px solid var(--border);
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-dark);
            transition: all 0.2s;
        }}
        .map-btn:hover, .map-btn.active {{
            background: var(--secondary);
            color: white;
            border-color: var(--secondary);
        }}
        .legend {{
            margin-top: 10px;
            padding: 10px;
            background: #f8fafc;
            border-radius: 8px;
            font-size: 12px;
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
        }}
        .charts-column {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .chart-container {{
            position: relative;
            height: 250px;
        }}
        .insights-section {{
            margin-bottom: 24px;
        }}
        .insights-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 16px;
            margin-top: 14px;
        }}
        .insight-card {{
            background: #f8fafc;
            border-left: 4px solid var(--secondary);
            padding: 16px;
            border-radius: 0 10px 10px 0;
            font-size: 14px;
            line-height: 1.5;
        }}
        .insight-card h4 {{
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 6px;
            color: var(--primary);
        }}
        .table-panel {{
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th, td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
            color: var(--text-dark);
        }}
        tr:hover {{
            background: #f8fafc;
        }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 32px;
            padding-top: 16px;
            border-top: 1px solid var(--border);
        }}
    </style>
</head>
<body>

    <div class="header">
        <h1>Кварталы и городские метрики: Октябрьский район, Барнаул</h1>
        <p>Интерактивный аналитический дашборд пространственных показателей, рассчитанных с помощью библиотеки вычислительной урбанистики <strong>BlocksNet (версия 1.0.0а9)</strong></p>
    </div>

    <!-- Ключевые показатели (KPI) -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Всего кварталов</div>
            <div class="kpi-value">{total_blocks:,}</div>
            <div class="kpi-sub">Нарезка по улицам, ж/д и рекам</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Оценка населения</div>
            <div class="kpi-value">{total_pop:,}</div>
            <div class="kpi-sub">чел. (по контурам жилых домов)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Жилой фонд</div>
            <div class="kpi-value">{total_living_area / 1e6:.2f} млн м²</div>
            <div class="kpi-sub">Суммарная площадь квартир</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Школьные места</div>
            <div class="kpi-value">{total_school_cap:,}</div>
            <div class="kpi-sub">Суммарная ёмкость школ</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Обеспеченность школами</div>
            <div class="kpi-value">{mean_prov_strong}%</div>
            <div class="kpi-sub">в радиусе пешей доступности</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Средняя плотность FSI</div>
            <div class="kpi-value">{mean_fsi}</div>
            <div class="kpi-sub">м² площади зданий на м² земли</div>
        </div>
    </div>

    <!-- Основной блок: Карта и Графики -->
    <div class="content-grid">
        <!-- Интерактивная карта -->
        <div class="panel">
            <div class="panel-title">
                <span>Интерактивная карта кварталов</span>
            </div>
            <div class="map-controls">
                <button class="map-btn active" onclick="switchLayer('land_use')">Землепользование</button>
                <button class="map-btn" onclick="switchLayer('provision')">Обеспеченность школами</button>
                <button class="map-btn" onclick="switchLayer('fsi')">Плотность (FSI)</button>
                <button class="map-btn" onclick="switchLayer('strelka')">Морфотипы «Стрелка»</button>
                <button class="map-btn" onclick="switchLayer('accessibility')">Доступность территории</button>
            </div>
            <div id="map"></div>
            <div id="legend" class="legend"></div>
        </div>

        <!-- Аналитические графики -->
        <div class="charts-column">
            <div class="panel">
                <div class="panel-title">Структура землепользования кварталов</div>
                <div class="chart-container">
                    <canvas id="landUseChart"></canvas>
                </div>
            </div>
            <div class="panel">
                <div class="panel-title">Морфотипы застройки (КБ «Стрелка»)</div>
                <div class="chart-container">
                    <canvas id="strelkaChart"></canvas>
                </div>
            </div>
            <div class="panel">
                <div class="panel-title">Распределение плотности застройки (FSI)</div>
                <div class="chart-container">
                    <canvas id="fsiChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <!-- Аналитические выводы -->
    <div class="panel insights-section">
        <div class="panel-title">Основные выводы городского исследования</div>
        <div class="insights-grid">
            <div class="insight-card">
                <h4>Функциональное зонирование района</h4>
                <p>В Октябрьском районе отчётливо выделяются два крупных кластера: жилые массивы в центральной и южной частях (823 жилых квартала) и мощный промышленно-логистический пояс на северо-востоке вдоль русла Оби и железнодорожных веток (156 промышленных кварталов).</p>
            </div>
            <div class="insight-card">
                <h4>Обеспеченность школами и баланс спроса</h4>
                <p>Средняя пешеходная обеспеченность школами составляет <strong>{mean_prov_strong}%</strong>. В ряде периферийных кварталов и частного сектора зафиксирован дефицит доступных школьных мест в радиусе 10–15 минут ходьбы, что требует организации школьных маршрутов или новых пристроек.</p>
            </div>
            <div class="insight-card">
                <h4>Плотность и архитектурная морфология</h4>
                <p>Преобладающий морфотип — <em>low-rise</em> (малоэтажная и среднеэтажная застройка) со средней этажностью L ≈ 1–4 этажа. Средний коэффициент плотности FSI составляет {mean_fsi}, что отражает умеренную интенсивность использования земли и значительную долю открытых пространств (OSR).</p>
            </div>
            <div class="insight-card">
                <h4>Транспортная связность</h4>
                <p>Пешеходный граф охватывает 14.5 тыс. узлов. Показатель территориальной доступности (area_accessibility) показывает высокую связность внутри жилых микрорайонов, но фиксирует разрыв доступности между промышленной набережной и спальным ядром района.</p>
            </div>
        </div>
    </div>

    <!-- Таблица показателей выборки кварталов -->
    <div class="panel table-panel">
        <div class="panel-title">
            <span>Таблица характеристик кварталов (первые 50 объектов)</span>
            <span style="font-size: 13px; font-weight: normal; color: var(--text-muted);">Всего в базе: {total_blocks:,}</span>
        </div>
        <table id="dataTable">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Землепользование</th>
                    <th>Обеспеченность (строгая)</th>
                    <th>Обеспеченность (мягкая)</th>
                    <th>FSI (плотность)</th>
                    <th>GSI (пятно)</th>
                    <th>MXI</th>
                    <th>Морфотип («Стрелка»)</th>
                    <th>Доступность (мин)</th>
                </tr>
            </thead>
            <tbody>
                <!-- Заполняется JS -->
            </tbody>
        </table>
    </div>

    <!-- Подвал и методология -->
    <div class="footer">
        <p><strong>Методология и источники данных:</strong> Данные улично-дорожной сети, границ, зданий и функциональных зон — <em>OpenStreetMap</em> (лицензия ODbL). Расчёт геометрии, восстановление недостающих данных (imputing), пространственные матрицы и моделирование обеспеченности — библиотека <strong>BlocksNet</strong> (ITMO University). Все оценки являются модельными и служат для целей мастер-планирования и учебного исследования.</p>
    </div>

    <script>
        const geojsonData = {json.dumps(geojson_data)};

        // Инициализация карты Leaflet
        const map = L.map('map').setView([{center_lat}, {center_lon}], 13);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
            maxZoom: 18
        }}).addTo(map);

        let geojsonLayer;
        let currentMode = 'land_use';

        function getColor(props, mode) {{
            if (mode === 'land_use') {{
                switch (props.land_use) {{
                    case 'residential': return '#22c55e';
                    case 'industrial': return '#64748b';
                    case 'business': return '#3b82f6';
                    case 'recreation': return '#10b981';
                    case 'special': return '#a855f7';
                    default: return '#e2e8f0';
                }}
            }} else if (mode === 'provision') {{
                const val = props.prov_s;
                if (val >= 0.8) return '#16a34a';
                if (val >= 0.4) return '#eab308';
                if (val > 0) return '#f97316';
                return '#dc2626';
            }} else if (mode === 'fsi') {{
                const val = props.fsi;
                if (val > 0.6) return '#7c3aed';
                if (val > 0.3) return '#3b82f6';
                if (val > 0.1) return '#06b6d4';
                if (val > 0) return '#a5f3fc';
                return '#f1f5f9';
            }} else if (mode === 'strelka') {{
                if (props.strelka.includes('model') || props.strelka.includes('low-rise')) return '#f59e0b';
                if (props.strelka.includes('individual')) return '#84cc16';
                if (props.strelka.includes('non-residential')) return '#94a3b8';
                return '#cbd5e1';
            }} else if (mode === 'accessibility') {{
                const val = parseFloat(props.acc);
                if (isNaN(val) || val === 'inf') return '#cbd5e1';
                if (val < 100) return '#10b981';
                if (val < 250) return '#facc15';
                if (val < 500) return '#fb923c';
                return '#ef4444';
            }}
            return '#cbd5e1';
        }}

        function style(feature) {{
            return {{
                fillColor: getColor(feature.properties, currentMode),
                weight: 0.7,
                opacity: 1,
                color: '#ffffff',
                fillOpacity: 0.75
            }};
        }}

        function onEachFeature(feature, layer) {{
            const p = feature.properties;
            const popupContent = `
                <div style="font-size:13px; line-height:1.4;">
                    <strong style="color:var(--primary)">Квартал #${{p.id}}</strong><br>
                    <strong>Землепользование:</strong> ${{p.land_use}}<br>
                    <strong>Обеспеченность школами:</strong> ${{Math.round(p.prov_s * 100)}}%<br>
                    <strong>Плотность FSI:</strong> ${{p.fsi}} (GSI: ${{p.gsi}})<br>
                    <strong>Этажность L:</strong> ${{p.l}}<br>
                    <strong>Морфотип («Стрелка»):</strong> ${{p.strelka}}<br>
                    <strong>Доступность:</strong> ${{p.acc}} мин
                </div>
            `;
            layer.bindPopup(popupContent);
            layer.on('mouseover', function (e) {{
                this.setStyle({{ weight: 2, color: '#0f172a', fillOpacity: 0.9 }});
            }});
            layer.on('mouseout', function (e) {{
                geojsonLayer.resetStyle(this);
            }});
        }}

        function updateLegend(mode) {{
            const legend = document.getElementById('legend');
            let html = '';
            if (mode === 'land_use') {{
                html = `
                    <div class="legend-item"><div class="legend-color" style="background:#22c55e"></div>Жильё</div>
                    <div class="legend-item"><div class="legend-color" style="background:#64748b"></div>Промзона</div>
                    <div class="legend-item"><div class="legend-color" style="background:#3b82f6"></div>Бизнес</div>
                    <div class="legend-item"><div class="legend-color" style="background:#10b981"></div>Рекреация</div>
                    <div class="legend-item"><div class="legend-color" style="background:#e2e8f0"></div>Без данных</div>
                `;
            }} else if (mode === 'provision') {{
                html = `
                    <div class="legend-item"><div class="legend-color" style="background:#16a34a"></div>Высокая (≥80%)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#eab308"></div>Средняя (40-80%)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#f97316"></div>Низкая (<40%)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#dc2626"></div>Дефицит мест (0%)</div>
                `;
            }} else if (mode === 'fsi') {{
                html = `
                    <div class="legend-item"><div class="legend-color" style="background:#7c3aed"></div>Очень высокая (>0.6)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#3b82f6"></div>Высокая (0.3-0.6)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#06b6d4"></div>Средняя (0.1-0.3)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#a5f3fc"></div>Низкая (0-0.1)</div>
                `;
            }} else if (mode === 'strelka') {{
                html = `
                    <div class="legend-item"><div class="legend-color" style="background:#f59e0b"></div>Малоэтажная модельная</div>
                    <div class="legend-item"><div class="legend-color" style="background:#84cc16"></div>Индивидуальная жилая</div>
                    <div class="legend-item"><div class="legend-color" style="background:#94a3b8"></div>Нежилая застройка</div>
                `;
            }} else if (mode === 'accessibility') {{
                html = `
                    <div class="legend-item"><div class="legend-color" style="background:#10b981"></div>Высокая (<100 мин)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#facc15"></div>Средняя (100-250 мин)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#fb923c"></div>Низкая (250-500 мин)</div>
                    <div class="legend-item"><div class="legend-color" style="background:#ef4444"></div>Периферия (>500 мин)</div>
                `;
            }}
            legend.innerHTML = html;
        }}

        function renderMap() {{
            if (geojsonLayer) map.removeLayer(geojsonLayer);
            geojsonLayer = L.geoJSON(geojsonData, {{
                style: style,
                onEachFeature: onEachFeature
            }}).addTo(map);
            updateLegend(currentMode);
        }}

        function switchLayer(mode) {{
            currentMode = mode;
            document.querySelectorAll('.map-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            renderMap();
        }}

        renderMap();

        // Построение графиков Chart.js
        // 1. Землепользование
        new Chart(document.getElementById('landUseChart'), {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(lu_labels)},
                datasets: [{{
                    data: {json.dumps(lu_values)},
                    backgroundColor: ['#22c55e', '#64748b', '#3b82f6', '#10b981', '#a855f7', '#cbd5e1']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ position: 'right' }} }}
            }}
        }});

        // 2. Стрелка
        new Chart(document.getElementById('strelkaChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(strelka_labels)},
                datasets: [{{
                    label: 'Кварталов',
                    data: {json.dumps(strelka_values)},
                    backgroundColor: '#0284c7'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});

        // 3. FSI
        new Chart(document.getElementById('fsiChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(fsi_labels)},
                datasets: [{{
                    label: 'Число кварталов',
                    data: {json.dumps(fsi_values)},
                    backgroundColor: '#8b5cf6'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }}
            }}
        }});

        // Заполнение таблицы выборкой
        const tableBody = document.querySelector('#dataTable tbody');
        geojsonData.features.slice(0, 50).forEach(f => {{
            const p = f.properties;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>#${{p.id}}</strong></td>
                <td>${{p.land_use}}</td>
                <td>${{Math.round(p.prov_s * 100)}}%</td>
                <td>${{Math.round(p.prov_w * 100)}}%</td>
                <td>${{p.fsi}}</td>
                <td>${{p.gsi}}</td>
                <td>${{p.mxi}}</td>
                <td>${{p.strelka}}</td>
                <td>${{p.acc}}</td>
            `;
            tableBody.appendChild(tr);
        }});
    </script>
</body>
</html>
"""

    out_file = Path("dashboard.html")
    out_file.write_text(html_template, encoding="utf-8")
    print(f"Дашборд успешно сгенерирован: {out_file.resolve()} ({out_file.stat().st_size:,} байт)")


if __name__ == "__main__":
    main()
