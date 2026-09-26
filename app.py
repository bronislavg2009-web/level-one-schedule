from flask import Flask, Response
import csv
import io
import urllib.request
import time
from html import escape

app = Flask(__name__)

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRwbM1H5sKbqfy3nv7l3sORZbwwqZMo4MHk1pjTbXZKoPio-oYYsZMpa1ix6KAfr1mED1IWsLlqaV-N/pub?gid=20260927&single=true&output=csv"

_last_good_rows = None


def fetch_rows():
    global _last_good_rows

    url = CSV_URL + "&t=" + str(int(time.time()))
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8-sig")

        rows = list(csv.reader(io.StringIO(text)))
        _last_good_rows = rows
        return rows

    except Exception:
        if _last_good_rows is not None:
            return _last_good_rows
        raise


def value(row, index):
    if index < len(row):
        return row[index].strip()
    return ""


def pretty_direction(direction):
    return {
        "HH": "HIP-HOP",
        "DH": "DANCEHALL",
        "JF": "JAZZ FUNK",
    }.get(direction.upper(), direction)


def parse_schedule(rows):
    header_rows = [
        index
        for index, row in enumerate(rows)
        if value(row, 0) == "Время" and value(row, 1) == "Блок"
    ]

    current = None
    schedule = []

    if header_rows:
        current_index = header_rows[0] + 1

        if current_index < len(rows):
            row = rows[current_index]

            if value(row, 0) and value(row, 1):
                current = {
                    "time": value(row, 0),
                    "block": value(row, 1),
                    "direction": pretty_direction(value(row, 2)),
                    "category": value(row, 3),
                    "participants": value(row, 4),
                    "status": value(row, 5),
                }

    if len(header_rows) >= 2:
        start = header_rows[1] + 1

        for row in rows[start:]:
            if not value(row, 0) or not value(row, 1):
                continue

            schedule.append(
                {
                    "time": value(row, 0),
                    "block": value(row, 1),
                    "direction": pretty_direction(value(row, 2)),
                    "category": value(row, 3),
                    "participants": value(row, 4),
                    "status": value(row, 5),
                }
            )

    if current is None:
        for item in schedule:
            if item["status"] == "ГРУППА ИДЁТ":
                current = item.copy()
                break

    next_block = None
    current_schedule_index = None

    if current:
        for index, item in enumerate(schedule):
            if item["time"] == current["time"] and item["block"] == current["block"]:
                current_schedule_index = index
                break

    start_index = current_schedule_index + 1 if current_schedule_index is not None else 0

    skip_blocks = {
        "Регистрация участников",
        "Начало LEVEL ONE",
        "Технический перерыв",
        "Ориентировочное окончание",
    }

    for item in schedule[start_index:]:
        if item["status"] in {"ГРУППА ЗАВЕРШЕНА", "ГРУППА ИДЁТ"}:
            continue

        if item["block"] in skip_blocks:
            continue

        next_block = item
        break

    return current, next_block, schedule


def render_current(current):
    if not current:
        return """
        <div class="current empty">
            <div class="waiting">Сейчас нет активной группы</div>
            <p>Организатор скоро запустит следующую группу.</p>
        </div>
        """

    details = []

    if current["direction"]:
        details.append(escape(current["direction"]))

    if current["category"]:
        details.append(escape(current["category"]))

    meta = " · ".join(details)

    return f"""
    <div class="current">
        <div class="live">● LIVE</div>
        <div class="current-time">{escape(current["time"])}</div>
        <h2>{escape(current["block"])}</h2>
        <p>{meta}</p>
    </div>
    """


def render_next(next_block):
    if not next_block:
        return """
        <div class="next">
            <strong>Следующих этапов нет</strong>
        </div>
        """

    details = []

    if next_block["direction"]:
        details.append(escape(next_block["direction"]))

    if next_block["category"]:
        details.append(escape(next_block["category"]))

    meta = " · ".join(details)

    return f"""
    <div class="next">
        <div class="next-time">{escape(next_block["time"])}</div>
        <strong>{escape(next_block["block"])}</strong>
        <div class="next-meta">{meta}</div>
    </div>
    """


def render_schedule(schedule):
    html = ""

    for item in schedule:
        status_class = ""

        if item["status"] == "ГРУППА ЗАВЕРШЕНА":
            status_class = "done"
        elif item["status"] == "ГРУППА ИДЁТ":
            status_class = "now"
        elif item["block"] == "Технический перерыв":
            status_class = "break"

        details = []

        if item["direction"]:
            details.append(escape(item["direction"]))

        if item["category"]:
            details.append(escape(item["category"]))

        meta = " · ".join(details)

        html += f"""
        <div class="schedule-row {status_class}">
            <div class="time">{escape(item["time"])}</div>

            <div class="info">
                <strong>{escape(item["block"])}</strong>
                <span>{meta}</span>
            </div>
        </div>
        """

    return html


@app.route("/")
def home():
    error_message = ""

    try:
        rows = fetch_rows()
        current, next_block, schedule = parse_schedule(rows)

    except Exception:
        current = None
        next_block = None
        schedule = []
        error_message = "Не удалось получить расписание. Страница попробует снова автоматически."

    current_html = render_current(current)
    next_html = render_next(next_block)
    rows_html = render_schedule(schedule)

    page = f"""
    <!DOCTYPE html>
    <html lang="ru">

    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1"
        >

        <meta
            http-equiv="refresh"
            content="10"
        >

        <meta
            name="theme-color"
            content="#050505"
        >

        <title>LEVEL ONE — Расписание</title>

        <style>
            :root {{
                --bg: #050505;
                --panel: #151515;
                --panel-2: #202020;
                --text: #f5f5f2;
                --muted: #a7a7a1;
                --line: #2c2c2a;
                --accent: #c0f840;
                --accent-2: #d3ff4d;
                --accent-soft: rgba(192, 248, 64, 0.10);
                --accent-border: rgba(192, 248, 64, 0.58);
            }}

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background:
                    radial-gradient(circle at 80% 8%, rgba(192, 248, 64, 0.08), transparent 24%),
                    linear-gradient(135deg, rgba(255,255,255,0.015) 25%, transparent 25%) 0 0 / 18px 18px,
                    var(--bg);
                color: var(--text);
                font-family: Arial, Helvetica, sans-serif;
            }}

            .container {{
                max-width: 700px;
                margin: auto;
                padding: 32px 16px 60px;
            }}

            .logo-wrap {{
                border-left: 5px solid var(--accent);
                padding-left: 14px;
                margin-bottom: 34px;
            }}

            .logo {{
                font-size: 34px;
                font-weight: 1000;
                letter-spacing: 3px;
                line-height: 1;
                color: #fff;
            }}

            .battle-tag {{
                display: inline-block;
                margin-top: 9px;
                color: var(--accent);
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 2.2px;
                text-transform: uppercase;
            }}

            .subtitle {{
                color: var(--muted);
                margin-top: 7px;
                font-size: 14px;
            }}

            .label {{
                color: var(--accent);
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 1.2px;
                margin: 0 0 9px;
                text-transform: uppercase;
            }}

            .current {{
                position: relative;
                overflow: hidden;
                border: 2px solid var(--accent);
                border-radius: 18px;
                padding: 24px;
                margin-bottom: 20px;
                background:
                    linear-gradient(135deg, var(--accent-soft), transparent 45%),
                    var(--panel);
            }}

            .current::after {{
                content: "";
                position: absolute;
                right: -28px;
                top: -42px;
                width: 120px;
                height: 120px;
                border: 18px solid rgba(192, 248, 64, 0.08);
                transform: rotate(28deg);
                pointer-events: none;
            }}

            .current.empty {{
                border-color: #444;
                background: var(--panel);
            }}

            .waiting {{
                font-size: 22px;
                font-weight: 900;
            }}

            .current-time {{
                position: relative;
                z-index: 1;
                font-size: 31px;
                font-weight: 1000;
                margin-bottom: 12px;
                color: #fff;
            }}

            .current h2 {{
                position: relative;
                z-index: 1;
                margin: 0 0 9px;
                font-size: 29px;
                font-weight: 1000;
                text-transform: uppercase;
            }}

            .current p {{
                position: relative;
                z-index: 1;
                margin: 4px 0 0;
                color: #deded9;
                font-size: 17px;
                font-weight: 700;
            }}

            .live {{
                position: relative;
                z-index: 1;
                display: inline-block;
                background: var(--accent);
                color: #050505;
                padding: 6px 10px;
                border-radius: 5px;
                font-weight: 1000;
                font-size: 12px;
                margin-bottom: 12px;
                letter-spacing: .5px;
            }}

            .next {{
                position: relative;
                background: var(--panel-2);
                border-left: 5px solid var(--accent);
                border-radius: 12px;
                padding: 19px;
                margin-bottom: 38px;
            }}

            .next-time {{
                font-size: 21px;
                font-weight: 1000;
                margin-bottom: 7px;
                color: #fff;
            }}

            .next strong {{
                font-size: 17px;
                text-transform: uppercase;
            }}

            .next-meta {{
                margin-top: 7px;
                color: var(--muted);
            }}

            h3 {{
                font-size: 22px;
                margin: 0 0 14px;
                text-transform: uppercase;
                letter-spacing: .3px;
            }}

            .schedule-row {{
                display: flex;
                gap: 16px;
                align-items: center;
                padding: 15px 4px;
                border-bottom: 1px solid var(--line);
            }}

            .schedule-row .time {{
                width: 125px;
                flex: 0 0 125px;
                font-size: 15px;
                font-weight: 900;
                color: #fff;
            }}

            .schedule-row .info {{
                display: flex;
                flex-direction: column;
                gap: 5px;
                min-width: 0;
            }}

            .schedule-row .info strong {{
                font-weight: 900;
            }}

            .schedule-row span {{
                color: var(--muted);
                font-size: 14px;
            }}

            .schedule-row.done {{
                opacity: .25;
            }}

            .schedule-row.now {{
                background:
                    linear-gradient(90deg, rgba(192,248,64,.13), transparent 75%);
                border-left: 4px solid var(--accent);
                padding-left: 12px;
                border-radius: 8px;
                opacity: 1;
            }}

            .schedule-row.now .time,
            .schedule-row.now .info strong {{
                color: var(--accent-2);
            }}

            .schedule-row.break {{
                opacity: .52;
                font-style: italic;
            }}

            .error {{
                background: #231616;
                border: 1px solid #7e3333;
                padding: 12px;
                border-radius: 10px;
                margin-bottom: 18px;
                color: #ffd4d4;
                font-size: 14px;
            }}

            .update-note {{
                margin-top: 30px;
                padding-top: 14px;
                border-top: 1px solid var(--line);
                color: #666;
                font-size: 12px;
                text-align: center;
            }}

            @media (max-width: 500px) {{
                .container {{
                    padding-top: 24px;
                }}

                .logo {{
                    font-size: 28px;
                }}

                .current {{
                    padding: 20px;
                }}

                .current h2 {{
                    font-size: 23px;
                }}

                .current-time {{
                    font-size: 25px;
                }}

                .schedule-row {{
                    gap: 11px;
                }}

                .schedule-row .time {{
                    width: 100px;
                    flex-basis: 100px;
                    font-size: 13px;
                }}

                .schedule-row .info strong {{
                    font-size: 15px;
                }}
            }}
        </style>
    </head>

    <body>

        <div class="container">

            <div class="logo-wrap">
                <div class="logo">LEVEL ONE</div>
                <div class="battle-tag">BEGINNERS BATTLE</div>
                <div class="subtitle">Школа танца RITM · расписание</div>
            </div>

            {f'<div class="error">{escape(error_message)}</div>' if error_message else ''}

            <div class="label">
                СЕЙЧАС ИДЁТ
            </div>

            {current_html}

            <div class="label">
                СЛЕДУЮЩАЯ ГРУППА
            </div>

            {next_html}

            <h3>
                Полное расписание
            </h3>

            {rows_html}

            <div class="update-note">
                Расписание обновляется автоматически каждые 10 секунд
            </div>

        </div>

    </body>

    </html>
    """

    response = Response(page)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


if __name__ == "__main__":
    app.run(debug=True)
