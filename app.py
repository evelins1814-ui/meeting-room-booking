import logging
import os
import re
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from domain import Invalid, parse_date, validate_booking, format_time

log = logging.getLogger(__name__)

def connect():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row, connect_timeout=10)

def initialize():
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS bookings (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            day DATE NOT NULL,
            start_min INTEGER NOT NULL,
            end_min INTEGER NOT NULL,
            CHECK (start_min >= 540 AND end_min <= 1200 AND start_min < end_min),
            CHECK (length(name) BETWEEN 1 AND 100)
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS bookings_day_idx ON bookings(day, start_min)')

@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(initialize)
    yield

app = FastAPI(title='Переговорка: 09:00–20:00', lifespan=lifespan)

@app.middleware('http')
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response

@app.exception_handler(Invalid)
async def invalid_handler(request, exc):
    return JSONResponse(status_code=400, content={'ok': False, 'error': str(exc)})

@app.exception_handler(psycopg.Error)
async def database_handler(request, exc):
    log.error('Database operation failed: %s', type(exc).__name__)
    return JSONResponse(status_code=503, content={'ok': False, 'error': 'База данных временно недоступна. Попробуйте позже.'})

def params(request, expected):
    query = request.query_params
    unknown = set(query.keys()) - set(expected)
    if unknown:
        raise Invalid('Неизвестные параметры: ' + ', '.join(sorted(unknown)))
    result = {}
    for key in expected:
        values = query.getlist(key)
        if len(values) != 1 or values[0] == '':
            raise Invalid(f'Укажите параметр {key} ровно один раз, с непустым значением.')
        result[key] = values[0]
    return result

def serialize(row):
    return {'id': row['id'], 'name': row['name'], 'date': row['day'].isoformat(),
            'from': format_time(row['start_min']), 'to': format_time(row['end_min'])}

@app.get('/')
def home():
    return {'service': 'Бронирование одной переговорной', 'hours': '09:00–20:00',
            'examples': ['/book?name=Анна&date=2026-11-10&from=10:00&to=11:00',
                         '/list?date=2026-11-10', '/cancel?id=1'],
            'docs': '/docs', 'notice': 'Публичное демо без авторизации: любой посетитель может посмотреть и отменить бронь. Не используйте персональные данные. Бесплатная база истекает 27 ноября 2026 года.'}

@app.get('/health')
def health():
    with connect() as conn:
        conn.execute('SELECT 1')
    return {'ok': True}

@app.get('/book')
def book(request: Request):
    p = params(request, ('name', 'date', 'from', 'to'))
    name, day, start, end = validate_booking(p['name'], p['date'], p['from'], p['to'])
    with connect() as conn:
        # Shared transaction lock for the single room; covers check and insert.
        conn.execute('SELECT pg_advisory_xact_lock(9212026)')
        conflict = conn.execute('''SELECT * FROM bookings
            WHERE day = %s AND start_min < %s AND end_min > %s
            ORDER BY start_min LIMIT 1''', (day, end, start)).fetchone()
        if conflict:
            return JSONResponse(status_code=409, content={'ok': False,
                'error': f'Время занято: бронь №{conflict["id"]}, {format_time(conflict["start_min"])}–{format_time(conflict["end_min"])}.'})
        row = conn.execute('''INSERT INTO bookings(name, day, start_min, end_min)
            VALUES (%s, %s, %s, %s) RETURNING *''', (name, day, start, end)).fetchone()
    return JSONResponse(status_code=201, content={'ok': True, 'booking': serialize(row)})

@app.get('/list')
def list_bookings(request: Request):
    day = parse_date(params(request, ('date',))['date'])
    with connect() as conn:
        rows = conn.execute('SELECT * FROM bookings WHERE day = %s ORDER BY start_min, id', (day,)).fetchall()
    return {'ok': True, 'date': day.isoformat(), 'bookings': [serialize(row) for row in rows]}

@app.get('/cancel')
def cancel(request: Request):
    value = params(request, ('id',))['id']
    if not re.fullmatch(r'[1-9][0-9]{0,18}', value) or int(value) > 9223372036854775807:
        raise Invalid('Номер брони должен быть положительным целым числом.')
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(9212026)')
        row = conn.execute('DELETE FROM bookings WHERE id = %s RETURNING *', (int(value),)).fetchone()
    if row is None:
        return JSONResponse(status_code=404, content={'ok': False, 'error': 'Бронь с таким номером не найдена или уже отменена.'})
    return {'ok': True, 'message': 'Бронь отменена.', 'booking': serialize(row)}
