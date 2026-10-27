import os
import shutil
import tempfile
import unittest
import datetime as dt
import tkinter as tk
from unittest.mock import patch

import app
from app import App, validate_appointment_datetime
from app import Database as RealDatabase


class FakeDate(dt.date):
    """Дата с «замороженным» текущим днём: 1 октября 2026."""
    @classmethod
    def today(cls):
        return cls(2026, 10, 1)


class FakeDateTime(dt.datetime):
    """Дата и время с «замороженным» текущим моментом: 1 октября 2026, 10:00."""
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 1, 10, 0)


class TestAppointmentValidation(unittest.TestCase):
    """Модульное тестирование функции проверки даты и времени записи"""

    def setUp(self):
        self.date_patcher = patch('app.dt.date', FakeDate)
        self.datetime_patcher = patch('app.dt.datetime', FakeDateTime)
        self.date_patcher.start()
        self.datetime_patcher.start()

    def tearDown(self):
        self.datetime_patcher.stop()
        self.date_patcher.stop()

    def check_error(self, date_value, time_value, message):
        with self.assertRaises(ValueError) as ctx:
            validate_appointment_datetime(date_value, time_value)
        self.assertEqual(str(ctx.exception), message)

    def test_appointment_datetime_validation(self):
        """Модульный тест. Проверка допустимого периода записи на приём."""
        print(" \n[Модульный тест] Проверка даты и времени записи на приём")

        # Проверка 1: дата в пределах 14 дней и время в будущем — ошибки нет
        self.assertIsNone(validate_appointment_datetime('2026-10-14', '15:00'))
        print(" ✓ 14.10.2026 15:00 → запись разрешена")

        # Проверка 2: прошедшая дата
        self.check_error('2026-09-30', '15:00', 'Нельзя записать пациента на прошедшую дату')
        print(" ✓ 30.09.2026 → «Нельзя записать пациента на прошедшую дату»")

        # Проверка 3: дата за пределами 14 дней
        self.check_error('2026-10-15', '15:00', 'Запись доступна только на ближайшие 14 календарных дней')
        print(" ✓ 15.10.2026 → «Запись доступна только на ближайшие 14 календарных дней»")

        # Проверка 4: сегодня, но время уже прошло (сейчас 10:00)
        self.check_error('2026-10-01', '09:00', 'Нельзя записать пациента на уже прошедшее время')
        print(" ✓ 01.10.2026 09:00 → «Нельзя записать пациента на уже прошедшее время»")

        # Проверка 5: неверный формат даты
        self.check_error('01.10.2026', '15:00', 'Введите дату в формате ГГГГ-ММ-ДД')
        print(" ✓ 01.10.2026 → «Введите дату в формате ГГГГ-ММ-ДД»")
        print(" Тест пройден ✓")


class TestCancelAppointmentFunctional(unittest.TestCase):
    """Функциональное тестирование отмены записи на приём"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db = RealDatabase(os.path.join(self.tmp_dir, 'test_clinic.db'))

    def tearDown(self):
        self.db.conn.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cancel_appointment(self):
        """Функциональный тест. Проверяет создание и отмену записи в базе данных."""
        print(" \n[Функциональный тест] Отмена записи на приём")

        patient_id = self.db.conn.execute('SELECT id FROM patients ORDER BY id').fetchone()['id']
        service_id = self.db.conn.execute("SELECT id FROM services WHERE name='Лечение кариеса'").fetchone()['id']
        doctor_id = self.db.doctors_for_service(service_id)[0]['id']
        date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        time = '16:30'

        # Создание записи: слот становится занятым
        aid = self.db.create_appointment(patient_id, doctor_id, service_id, date, time)
        self.assertTrue(self.db.occupied(doctor_id, date, time))
        print(f" Запись создана: id = {aid}, {date} {time}, слот занят")

        # Отмена записи: статус и причина сохраняются в базе
        self.db.cancel(aid, 'Пациент заболел')
        row = self.db.conn.execute('SELECT status, cancel_reason FROM appointments WHERE id=?', (aid,)).fetchone()
        self.assertEqual(row['status'], 'Отменена')
        self.assertEqual(row['cancel_reason'], 'Пациент заболел')
        print(f" Статус : {row['status']}, причина : {row['cancel_reason']}")

        # Слот освобождается
        self.assertFalse(self.db.occupied(doctor_id, date, time))
        print(" Слот освобождён для новой записи")

        # Повторная отмена и отмена несуществующей записи
        with self.assertRaises(ValueError) as ctx:
            self.db.cancel(aid, 'Повторная отмена')
        self.assertEqual(str(ctx.exception), 'Запись уже отменена')
        with self.assertRaises(ValueError) as ctx:
            self.db.cancel(999999, '')
        self.assertEqual(str(ctx.exception), 'Запись не найдена')
        print(" Повторная отмена → «Запись уже отменена»")
        print(" Несуществующая запись → «Запись не найдена»")
        print(" Тест пройден ✓")


class TestLoginUI(unittest.TestCase):
    """UI-тестирование окна авторизации"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmp_dir, 'test_clinic.db')
        self.db_patcher = patch('app.Database', lambda: RealDatabase(db_path))
        self.db_patcher.start()
        self.messagebox_patcher = patch('tkinter.messagebox.showerror')
        self.mock_messagebox = self.messagebox_patcher.start()
        self.window = App()
        self.window.withdraw()

    def tearDown(self):
        self.messagebox_patcher.stop()
        self.db_patcher.stop()
        self.window.db.conn.close()
        self.window.destroy()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_login_wrong_password_error(self):
        """UI-тест. Проверяет, что вход с неверным паролем отображает ошибку."""
        print(" \n[UI-тест] Проверка входа с неверным паролем")

        self.window.login('admin', 'wrong_password')

        # Проверяем, что messagebox.showerror был вызван
        self.mock_messagebox.assert_called_once()
        args = self.mock_messagebox.call_args[0]
        self.assertEqual(args[0], 'Ошибка входа')
        self.assertEqual(args[1], 'Неправильный логин или пароль')

        # Проверяем, что пользователь не авторизован
        self.assertIsNone(self.window.user)

        print("Действие: нажатие кнопки «Войти» с неверным паролем")
        print("Ожидаемый результат: сообщение «Неправильный логин или пароль»")
        print("Фактический результат: сообщение показано, вход не выполнен ✓")


if __name__ == '__main__':
    unittest.main(verbosity=2)
