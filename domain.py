import re
from datetime import date

class Invalid(ValueError):
    pass

def parse_date(value):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise Invalid('Дата должна быть в формате ГГГГ-ММ-ДД.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise Invalid('Такой календарной даты не существует.')

def parse_time(value):
    if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
        raise Invalid('Время должно быть в формате ЧЧ:ММ, от 00:00 до 23:59.')
    return int(value[:2]) * 60 + int(value[3:])

def validate_booking(name, day, start, end):
    name = name.strip()
    if not name or len(name) > 100 or any(ord(c) < 32 for c in name):
        raise Invalid('Имя должно содержать от 1 до 100 символов без управляющих символов.')
    day = parse_date(day)
    start, end = parse_time(start), parse_time(end)
    if start >= end:
        raise Invalid('Начало брони должно быть раньше окончания.')
    if start < 540 or end > 1200:
        raise Invalid('Переговорка работает с 09:00 до 20:00.')
    return name, day, start, end

def format_time(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'
