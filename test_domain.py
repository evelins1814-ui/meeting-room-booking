import unittest
from domain import Invalid, parse_date, parse_time, validate_booking, format_time

class ValidationTests(unittest.TestCase):
    def test_valid(self):
        name, day, start, end = validate_booking(' Анна ', '2026-11-10', '09:00', '20:00')
        self.assertEqual((name, str(day), start, end), ('Анна', '2026-11-10', 540, 1200))
    def test_invalid_dates(self):
        for value in ('2026-02-30', '2026-1-01', '0000-01-01', '10.11.2026', ''):
            with self.subTest(value=value), self.assertRaises(Invalid):
                parse_date(value)
    def test_leap_date(self):
        self.assertEqual(str(parse_date('2028-02-29')), '2028-02-29')
    def test_invalid_times(self):
        for value in ('9:00', '24:00', '10:60', '10:00:00', ''):
            with self.subTest(value=value), self.assertRaises(Invalid):
                parse_time(value)
    def test_invalid_intervals(self):
        for start, end in (('08:59', '10:00'), ('19:00', '20:01'), ('10:00', '10:00'), ('11:00', '10:00')):
            with self.subTest(start=start, end=end), self.assertRaises(Invalid):
                validate_booking('Анна', '2026-11-10', start, end)
    def test_invalid_name(self):
        for name in (' ', 'x' * 101, 'a\nb'):
            with self.subTest(name=name), self.assertRaises(Invalid):
                validate_booking(name, '2026-11-10', '10:00', '11:00')
    def test_format(self):
        self.assertEqual(format_time(540), '09:00')
        self.assertEqual(format_time(1200), '20:00')

if __name__ == '__main__':
    unittest.main()
