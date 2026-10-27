import os
import shutil
import tempfile
import unittest
import datetime as dt
from unittest.mock import patch

from app import App, validate_account
from app import Database as RealDatabase


class TestAccountValidation(unittest.TestCase):
    """Модульное тестирование функции проверки данных учётной записи администратора"""

    def check_error(self, full_name, login, password, message):
        with self.assertRaises(ValueError) as ctx:
            validate_account(full_name, login, password)
        self.assertEqual(str(ctx.exception), message)

    def test_account_validation(self):
        """Модульный тест. Проверка ФИО, логина и пароля учётной записи."""
        print(' \n[Модульный тест] Проверка данных учётной записи администратора')

        # Проверка 1: корректные данные — ошибки нет
        self.assertIsNone(validate_account('Орлова Ирина Павловна', 'orlova.ip', 'Admin2026'))
        print(' ✓ Орлова И.П. / orlova.ip / Admin2026 → данные приняты')

        # Проверка 2: пустое ФИО
        self.check_error('  ', 'orlova.ip', 'Admin2026', 'Введите ФИО сотрудника')
        print(' ✓ Пустое ФИО → «Введите ФИО сотрудника»')

        # Проверка 3: логин с кириллицей и слишком короткий логин
        login_error = 'Логин должен содержать от 3 до 20 латинских букв, цифр или символов «_» и «.»'
        self.check_error('Орлова Ирина Павловна', 'орлова', 'Admin2026', login_error)
        self.check_error('Орлова Ирина Павловна', 'ip', 'Admin2026', login_error)
        print(' ✓ Логин «орлова» и «ip» → «Логин должен содержать от 3 до 20 латинских букв...»')

        # Проверка 4: короткий пароль
        self.check_error('Орлова Ирина Павловна', 'orlova.ip', 'a1', 'Пароль должен содержать не менее 6 символов')
        print(' ✓ Пароль «a1» → «Пароль должен содержать не менее 6 символов»')

        # Проверка 5: пароль без цифр
        self.check_error('Орлова Ирина Павловна', 'orlova.ip', 'password', 'Пароль должен содержать буквы и цифры')
        print(' ✓ Пароль «password» → «Пароль должен содержать буквы и цифры»')

        # Проверка 6: при редактировании пароль не передаётся и не проверяется
        self.assertIsNone(validate_account('Орлова Ирина Павловна', 'orlova.ip', None))
        print(' ✓ Редактирование без смены пароля → данные приняты')
        print(' Тест пройден ✓')


class TestDeleteDoctorFunctional(unittest.TestCase):
    """Функциональное тестирование удаления врача из справочника"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db = RealDatabase(os.path.join(self.tmp_dir, 'test_clinic.db'))

    def tearDown(self):
        self.db.conn.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_delete_doctor(self):
        """Функциональный тест. Добавление врача, запрет удаления при активной записи, удаление после отмены."""
        print(' \n[Функциональный тест] Удаление врача из справочника')

        # Главный врач добавляет нового врача — ему назначается стандартный график
        did = self.db.save_doctor({'full_name': 'Лебедев Олег Викторович', 'specialization': 'Стоматолог-хирург',
                                   'experience': '7', 'qualification': 'Врач первой категории'})
        self.assertIn(did, [d['id'] for d in self.db.doctors()])
        self.assertEqual(len(self.db.work_schedule(did)), 7)
        print(f' Врач добавлен: id = {did}, график на 7 дней недели')

        # Администратор записывает к нему пациента
        patient_id = self.db.conn.execute('SELECT id FROM patients ORDER BY id').fetchone()['id']
        service_id = self.db.conn.execute("SELECT id FROM services WHERE name='Имплантация'").fetchone()['id']
        date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        aid = self.db.create_appointment(patient_id, did, service_id, date, '15:00')
        print(f' Создана запись на приём: id = {aid}, {date} 15:00')

        # Удаление врача с активной записью запрещено
        with self.assertRaises(ValueError) as ctx:
            self.db.delete_doctor(did)
        self.assertEqual(str(ctx.exception), 'Нельзя удалить врача: у него есть активные записи на приём')
        print(' Удаление с активной записью → «Нельзя удалить врача: у него есть активные записи на приём»')

        # После отмены записи врач удаляется из справочника, история сохраняется
        self.db.cancel(aid, 'Врач увольняется')
        self.db.delete_doctor(did)
        self.assertNotIn(did, [d['id'] for d in self.db.doctors()])
        self.assertNotIn(did, [d['id'] for d in self.db.doctors_for_service(service_id)])
        self.assertEqual(self.db.work_schedule(did), {})
        history = self.db.appointments(doctor_id=did)
        self.assertEqual(len(history), 1)
        print(' После отмены записи врач удалён: недоступен для записи, график очищен')
        print(f' История приёмов сохранена: {len(history)} запись, статус «{history[0]["status"]}»')

        # Удаление несуществующего врача
        with self.assertRaises(ValueError) as ctx:
            self.db.delete_doctor(999999)
        self.assertEqual(str(ctx.exception), 'Врач не найден')
        print(' Несуществующий врач → «Врач не найден»')
        print(' Тест пройден ✓')


class TestRoleAccessUI(unittest.TestCase):
    """UI-тестирование разграничения доступа по ролям"""

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

    def test_role_menu_and_blocked_login(self):
        """UI-тест. Меню зависит от роли; заблокированный администратор не может войти."""
        print(' \n[UI-тест] Разграничение доступа по ролям')
        chief_sections = ['График работы', 'Учётные записи']
        admin_sections = ['Расписание', 'Запись на приём', 'Поиск пациента', 'Отчётность']

        # Вход главного врача: доступны только разделы администрирования
        self.window.login('chief', 'chief')
        self.assertEqual(self.window.user['role'], 'chief')
        self.assertEqual(list(self.window.nav_buttons), ['Врачи', 'График работы', 'Учётные записи'])
        for name in admin_sections:
            self.assertNotIn(name, self.window.nav_buttons)
        print(' Вход «chief»: меню «Врачи», «График работы», «Учётные записи», разделов записи пациентов нет ✓')

        # Главный врач блокирует администратора и выходит
        admin_id = self.window.db.conn.execute("SELECT id FROM accounts WHERE login='admin'").fetchone()['id']
        self.window.db.set_account_active(admin_id, False)
        self.window.show_login()
        self.window.user = None

        # Заблокированный администратор не может войти
        self.window.login('admin', 'admin')
        self.mock_messagebox.assert_called_once()
        self.assertEqual(self.mock_messagebox.call_args[0][1], 'Неправильный логин или пароль')
        self.assertIsNone(self.window.user)
        print(' Вход заблокированного «admin»: сообщение «Неправильный логин или пароль», вход не выполнен ✓')

        # После разблокировки администратор входит, но разделов главного врача не видит
        self.window.db.set_account_active(admin_id, True)
        self.window.login('admin', 'admin')
        self.assertEqual(self.window.user['role'], 'admin')
        for name in chief_sections:
            self.assertNotIn(name, self.window.nav_buttons)
        for name in admin_sections:
            self.assertIn(name, self.window.nav_buttons)
        print(' Вход разблокированного «admin»: разделы записи пациентов есть, разделов главного врача нет ✓')


if __name__ == '__main__':
    unittest.main(verbosity=2)
