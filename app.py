import os
import re
import sqlite3
import hashlib
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assol_clinic.db')

DOCTORS = [
    ('Иванова Анна Сергеевна', 'Стоматолог-терапевт', 8, 'Врач первой категории'),
    ('Петров Дмитрий Андреевич', 'Стоматолог-терапевт', 12, 'Врач высшей категории'),
    ('Соколова Мария Викторовна', 'Стоматолог-терапевт', 6, 'Врач первой категории'),
    ('Кузнецов Павел Игоревич', 'Стоматолог-ортопед', 15, 'Врач высшей категории'),
    ('Морозов Алексей Николаевич', 'Стоматолог-хирург', 10, 'Врач первой категории'),
]
SERVICES = [
    ('Консультация стоматолога', 'Диагностика', 1200),
    ('Лечение кариеса', 'Терапия', 3500),
    ('Профессиональная чистка', 'Профилактика', 2800),
    ('Протезирование', 'Ортопедия', 15000),
    ('Имплантация', 'Хирургия', 30000),
    ('Лечение дёсен', 'Терапия', 4500),
]
SERVICE_SPECIALIZATIONS = {
    'Диагностика': ['Стоматолог-терапевт', 'Стоматолог-ортопед', 'Стоматолог-хирург'],
    'Терапия': ['Стоматолог-терапевт'],
    'Профилактика': ['Стоматолог-терапевт'],
    'Ортопедия': ['Стоматолог-ортопед'],
    'Хирургия': ['Стоматолог-хирург'],
}
SLOT_TIMES = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00']

# ===== Модуль главного врача =====
ROLE_NAMES = {'admin': 'Администратор', 'chief': 'Главный врач'}
SPECIALIZATIONS = ['Стоматолог-терапевт', 'Стоматолог-ортопед', 'Стоматолог-хирург']
QUALIFICATIONS = ['Без категории', 'Врач второй категории', 'Врач первой категории', 'Врач высшей категории']
WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
# Время начала и окончания приёма в графике работы (шаг 30 минут)
WORK_TIMES = ['08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30', '12:00', '12:30',
              '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30', '17:00', '17:30',
              '18:00', '18:30', '19:00', '19:30', '20:00']
DEFAULT_START, DEFAULT_END = '09:00', '17:30'


def hash_password(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def validate_password(password):
    """Проверяет надёжность пароля учётной записи администратора."""
    if len(password) < 6:
        raise ValueError('Пароль должен содержать не менее 6 символов')
    if not re.search(r'[A-Za-zА-Яа-яЁё]', password) or not re.search(r'\d', password):
        raise ValueError('Пароль должен содержать буквы и цифры')


def validate_account(full_name, login, password=None):
    """Проверяет данные учётной записи администратора перед сохранением.
    password=None означает, что пароль не меняется (редактирование)."""
    if not full_name.strip():
        raise ValueError('Введите ФИО сотрудника')
    if not re.fullmatch(r'[A-Za-z0-9_.]{3,20}', login):
        raise ValueError('Логин должен содержать от 3 до 20 латинских букв, цифр или символов «_» и «.»')
    if password is not None:
        validate_password(password)


def validate_doctor(full_name, specialization, experience, qualification):
    """Проверяет данные врача перед сохранением в справочник."""
    if not full_name.strip():
        raise ValueError('Введите ФИО врача')
    if specialization not in SPECIALIZATIONS:
        raise ValueError('Выберите специализацию из списка')
    try:
        years = int(str(experience).strip())
    except ValueError:
        raise ValueError('Стаж должен быть целым числом от 0 до 60')
    if years < 0 or years > 60:
        raise ValueError('Стаж должен быть целым числом от 0 до 60')
    if qualification not in QUALIFICATIONS:
        raise ValueError('Выберите квалификацию из списка')
    return years


def validate_work_hours(start, end):
    """Проверяет время начала и окончания приёма в графике работы врача."""
    if start not in WORK_TIMES or end not in WORK_TIMES:
        raise ValueError('Выберите время из списка')
    if start >= end:
        raise ValueError('Время начала приёма должно быть раньше времени окончания')


def slots_for_hours(start, end):
    """Возвращает слоты приёма, попадающие в рабочее время [start; end)."""
    return [t for t in SLOT_TIMES if start <= t < end]


def validate_appointment_datetime(date_value, time_value):
    """Проверяет, что запись можно оформить только на текущий момент или будущее в пределах 14 календарных дней."""
    try:
        appointment_date = dt.date.fromisoformat(date_value)
    except ValueError:
        raise ValueError('Введите дату в формате ГГГГ-ММ-ДД')

    today = dt.date.today()
    last_date = today + dt.timedelta(days=13)
    if appointment_date < today:
        raise ValueError('Нельзя записать пациента на прошедшую дату')
    if appointment_date > last_date:
        raise ValueError('Запись доступна только на ближайшие 14 календарных дней')

    try:
        appointment_time = dt.datetime.strptime(time_value, '%H:%M').time()
    except ValueError:
        raise ValueError('Выберите корректное время приёма')

    appointment_dt = dt.datetime.combine(appointment_date, appointment_time)
    if appointment_dt <= dt.datetime.now():
        raise ValueError('Нельзя записать пациента на уже прошедшее время')


class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.init_schema()
        self.seed()

    def init_schema(self):
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            experience INTEGER NOT NULL,
            qualification TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS work_schedule (
            id INTEGER PRIMARY KEY,
            doctor_id INTEGER NOT NULL REFERENCES doctors(id),
            weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            UNIQUE(doctor_id, weekday)
        );
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            passport TEXT NOT NULL,
            notification TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY,
            patient_id INTEGER NOT NULL REFERENCES patients(id),
            doctor_id INTEGER NOT NULL REFERENCES doctors(id),
            service_id INTEGER NOT NULL REFERENCES services(id),
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Новая',
            source TEXT NOT NULL DEFAULT 'Телефон',
            cancel_reason TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(doctor_id, date, time)
        );
        CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(full_name);
        CREATE INDEX IF NOT EXISTS idx_patients_passport ON patients(passport);
        CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);
        ''')
        # Если база создана предыдущей версией АРМ — добавляем признак активности врача
        cols = [r['name'] for r in self.conn.execute('PRAGMA table_info(doctors)').fetchall()]
        if 'active' not in cols:
            self.conn.execute('ALTER TABLE doctors ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
        self.conn.commit()

    def seed(self):
        cur = self.conn.cursor()
        cur.execute('SELECT COUNT(*) FROM accounts')
        if cur.fetchone()[0] == 0:
            cur.execute('INSERT INTO accounts(full_name,login,password_hash,role,active) VALUES(?,?,?,?,1)',
                        ('Администратор клиники', 'admin', hash_password('admin'), 'admin'))
        if cur.execute("SELECT COUNT(*) FROM accounts WHERE role='chief'").fetchone()[0] == 0:
            cur.execute('INSERT INTO accounts(full_name,login,password_hash,role,active) VALUES(?,?,?,?,1)',
                        ('Главный врач клиники', 'chief', hash_password('chief'), 'chief'))
        if cur.execute('SELECT COUNT(*) FROM doctors').fetchone()[0] == 0:
            cur.executemany('INSERT INTO doctors(full_name,specialization,experience,qualification) VALUES(?,?,?,?)', DOCTORS)
        if cur.execute('SELECT COUNT(*) FROM work_schedule').fetchone()[0] == 0:
            # Начальный график: клиника работает ежедневно, приём с 09:00 до 17:30
            for d in cur.execute('SELECT id FROM doctors').fetchall():
                cur.executemany('INSERT INTO work_schedule(doctor_id,weekday,start_time,end_time) VALUES(?,?,?,?)',
                                [(d['id'], wd, DEFAULT_START, DEFAULT_END) for wd in range(7)])
        if cur.execute('SELECT COUNT(*) FROM services').fetchone()[0] == 0:
            cur.executemany('INSERT INTO services(name,category,price) VALUES(?,?,?)', SERVICES)
        if cur.execute('SELECT COUNT(*) FROM patients').fetchone()[0] == 0:
            patients = [
                ('Смирнова Елена Олеговна', '1988-04-15', '+7 900 111-22-33', '6501 123456', 'SMS-сообщение'),
                ('Ковалёв Артём Сергеевич', '1995-09-02', '+7 900 222-33-44', '6502 234567', 'Обратный звонок'),
                ('Васильева Ольга Петровна', '1979-12-20', '+7 900 333-44-55', '6503 345678', 'SMS-сообщение'),
            ]
            cur.executemany('INSERT INTO patients(full_name,birth_date,phone,passport,notification) VALUES(?,?,?,?,?)', patients)
        self.conn.commit()
        if cur.execute('SELECT COUNT(*) FROM appointments').fetchone()[0] == 0:
            today = dt.date.today()
            pids = [r['id'] for r in cur.execute('SELECT id FROM patients ORDER BY id').fetchall()]
            dids = [r['id'] for r in cur.execute('SELECT id FROM doctors ORDER BY id').fetchall()]
            sids = [r['id'] for r in cur.execute('SELECT id FROM services ORDER BY id').fetchall()]
            demo = [
                (pids[0], dids[0], sids[1], today.isoformat(), '10:00', 'Подтверждена', 'Телефон', None),
                (pids[1], dids[3], sids[3], (today + dt.timedelta(days=1)).isoformat(), '14:30', 'Новая', 'Телефон', None),
                (pids[2], dids[4], sids[4], (today + dt.timedelta(days=2)).isoformat(), '11:30', 'Новая', 'Телефон', None),
            ]
            cur.executemany('''INSERT INTO appointments(patient_id,doctor_id,service_id,date,time,status,source,cancel_reason,created_at)
                               VALUES(?,?,?,?,?,?,?,?,?)''',
                            [(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7],
                              dt.datetime.now().isoformat(timespec='seconds')) for a in demo])
        self.conn.commit()

    def authenticate(self, login, password):
        row = self.conn.execute('SELECT * FROM accounts WHERE login=? AND active=1', (login,)).fetchone()
        if row and row['password_hash'] == hash_password(password):
            return row
        return None

    def doctors(self, include_inactive=False):
        sql = 'SELECT * FROM doctors'
        if not include_inactive:
            sql += ' WHERE active=1'
        return self.conn.execute(sql + ' ORDER BY full_name').fetchall()

    def services(self):
        return self.conn.execute('SELECT * FROM services ORDER BY category,name').fetchall()

    def doctors_for_service(self, service_id):
        service = self.conn.execute('SELECT category FROM services WHERE id=?', (service_id,)).fetchone()
        if not service:
            return []
        allowed = SERVICE_SPECIALIZATIONS.get(service['category'], [])
        if not allowed:
            return self.doctors()
        marks = ','.join('?' * len(allowed))
        return self.conn.execute(f'SELECT * FROM doctors WHERE active=1 AND specialization IN ({marks}) ORDER BY full_name',
                                 allowed).fetchall()

    def search_patients(self, q):
        q = q.strip()
        like = f'%{q}%'
        return self.conn.execute('''SELECT * FROM patients
            WHERE full_name LIKE ? OR phone LIKE ? OR passport LIKE ? ORDER BY full_name''',
                                 (like, like, like)).fetchall()

    def patient(self, pid):
        return self.conn.execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()

    def save_patient(self, data):
        if data.get('id'):
            self.conn.execute('''UPDATE patients SET full_name=?,birth_date=?,phone=?,passport=?,notification=? WHERE id=?''',
                              (data['full_name'], data['birth_date'], data['phone'], data['passport'], data['notification'], data['id']))
            pid = data['id']
        else:
            cur = self.conn.execute('''INSERT INTO patients(full_name,birth_date,phone,passport,notification) VALUES(?,?,?,?,?)''',
                                    (data['full_name'], data['birth_date'], data['phone'], data['passport'], data['notification']))
            pid = cur.lastrowid
        self.conn.commit()
        return pid

    def appointments(self, start=None, end=None, doctor_id=None, patient_id=None, include_cancelled=True):
        sql = '''SELECT a.*, p.full_name patient_name, p.phone, p.notification, d.full_name doctor_name,
                        d.specialization, s.name service_name, s.category, s.price
                 FROM appointments a JOIN patients p ON p.id=a.patient_id
                 JOIN doctors d ON d.id=a.doctor_id JOIN services s ON s.id=a.service_id WHERE 1=1'''
        args = []
        if start:
            sql += ' AND a.date>=?'; args.append(start)
        if end:
            sql += ' AND a.date<=?'; args.append(end)
        if doctor_id:
            sql += ' AND a.doctor_id=?'; args.append(doctor_id)
        if patient_id:
            sql += ' AND a.patient_id=?'; args.append(patient_id)
        if not include_cancelled:
            sql += " AND a.status!='Отменена'"
        sql += ' ORDER BY a.date,a.time'
        return self.conn.execute(sql, args).fetchall()

    def occupied(self, doctor_id, date, time, except_id=None):
        sql = "SELECT id FROM appointments WHERE doctor_id=? AND date=? AND time=? AND status!='Отменена'"
        args = [doctor_id, date, time]
        if except_id:
            sql += ' AND id!=?'; args.append(except_id)
        return self.conn.execute(sql, args).fetchone() is not None

    def create_appointment(self, patient_id, doctor_id, service_id, date, time):
        validate_appointment_datetime(date, time)
        if time not in self.doctor_slots(doctor_id, date):
            raise ValueError('Врач не принимает в выбранное время по графику работы')
        if self.occupied(doctor_id, date, time):
            raise ValueError('Данное время уже занято')
        doctors = {r['id'] for r in self.doctors_for_service(service_id)}
        if doctor_id not in doctors:
            raise ValueError('Выбранный врач не оказывает указанную услугу')
        cur = self.conn.execute('''INSERT INTO appointments(patient_id,doctor_id,service_id,date,time,status,source,created_at)
                                 VALUES(?,?,?,?,?,'Новая','Телефон',?)''',
                                (patient_id, doctor_id, service_id, date, time,
                                 dt.datetime.now().isoformat(timespec='seconds')))
        self.conn.commit()
        return cur.lastrowid

    def update_appointment(self, aid, patient_id, doctor_id, service_id, date, time):
        validate_appointment_datetime(date, time)
        if time not in self.doctor_slots(doctor_id, date):
            raise ValueError('Врач не принимает в выбранное время по графику работы')
        if self.occupied(doctor_id, date, time, aid):
            raise ValueError('Данное время уже занято')
        self.conn.execute('''UPDATE appointments SET patient_id=?,doctor_id=?,service_id=?,date=?,time=? WHERE id=?''',
                          (patient_id, doctor_id, service_id, date, time, aid))
        self.conn.commit()

    def cancel(self, aid, reason):
        row = self.conn.execute('SELECT status FROM appointments WHERE id=?', (aid,)).fetchone()
        if not row:
            raise ValueError('Запись не найдена')
        if row['status'] == 'Отменена':
            raise ValueError('Запись уже отменена')
        self.conn.execute("UPDATE appointments SET status='Отменена', cancel_reason=? WHERE id=?", (reason or None, aid))
        self.conn.commit()

    def complete(self, aid):
        self.conn.execute("UPDATE appointments SET status='Выполнена' WHERE id=?", (aid,))
        self.conn.commit()

    # ===== Учётные записи администраторов (главный врач) =====
    def accounts(self):
        return self.conn.execute("SELECT * FROM accounts WHERE role='admin' ORDER BY full_name").fetchall()

    def account(self, aid):
        return self.conn.execute('SELECT * FROM accounts WHERE id=?', (aid,)).fetchone()

    def save_account(self, data):
        """Создаёт учётную запись администратора (если нет id) или изменяет ФИО и логин."""
        full_name, login = data['full_name'].strip(), data['login'].strip()
        password = data.get('password') if not data.get('id') else None
        validate_account(full_name, login, password)
        try:
            if data.get('id'):
                if not self.account(data['id']):
                    raise ValueError('Учётная запись не найдена')
                self.conn.execute('UPDATE accounts SET full_name=?, login=? WHERE id=?',
                                  (full_name, login, data['id']))
                aid = data['id']
            else:
                cur = self.conn.execute("INSERT INTO accounts(full_name,login,password_hash,role,active) VALUES(?,?,?,'admin',1)",
                                        (full_name, login, hash_password(password)))
                aid = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError('Учётная запись с таким логином уже существует')
        self.conn.commit()
        return aid

    def change_password(self, aid, password):
        validate_password(password)
        if not self.account(aid):
            raise ValueError('Учётная запись не найдена')
        self.conn.execute('UPDATE accounts SET password_hash=? WHERE id=?', (hash_password(password), aid))
        self.conn.commit()

    def set_account_active(self, aid, active):
        row = self.account(aid)
        if not row:
            raise ValueError('Учётная запись не найдена')
        if row['role'] == 'chief':
            raise ValueError('Нельзя заблокировать учётную запись главного врача')
        self.conn.execute('UPDATE accounts SET active=? WHERE id=?', (1 if active else 0, aid))
        self.conn.commit()

    def delete_account(self, aid):
        row = self.account(aid)
        if not row:
            raise ValueError('Учётная запись не найдена')
        if row['role'] == 'chief':
            raise ValueError('Нельзя удалить учётную запись главного врача')
        self.conn.execute('DELETE FROM accounts WHERE id=?', (aid,))
        self.conn.commit()

    # ===== Справочник врачей (главный врач) =====
    def doctor(self, did):
        return self.conn.execute('SELECT * FROM doctors WHERE id=?', (did,)).fetchone()

    def save_doctor(self, data):
        """Добавляет нового врача (если нет id) или обновляет данные существующего."""
        years = validate_doctor(data['full_name'], data['specialization'], data['experience'], data['qualification'])
        full_name = data['full_name'].strip()
        same = self.conn.execute('SELECT id FROM doctors WHERE full_name=? AND specialization=? AND active=1 AND id!=?',
                                 (full_name, data['specialization'], data.get('id') or 0)).fetchone()
        if same:
            raise ValueError('Врач с таким ФИО и специализацией уже есть в справочнике')
        if data.get('id'):
            old = self.doctor(data['id'])
            if not old:
                raise ValueError('Врач не найден')
            if old['specialization'] != data['specialization'] and self.future_appointments(data['id']):
                raise ValueError('Нельзя сменить специализацию: у врача есть активные записи на приём')
            self.conn.execute('UPDATE doctors SET full_name=?,specialization=?,experience=?,qualification=? WHERE id=?',
                              (full_name, data['specialization'], years, data['qualification'], data['id']))
            did = data['id']
        else:
            cur = self.conn.execute('INSERT INTO doctors(full_name,specialization,experience,qualification,active) VALUES(?,?,?,?,1)',
                                    (full_name, data['specialization'], years, data['qualification']))
            did = cur.lastrowid
            # Новому врачу назначается стандартный график, который главный врач затем может изменить
            self.conn.executemany('INSERT INTO work_schedule(doctor_id,weekday,start_time,end_time) VALUES(?,?,?,?)',
                                  [(did, wd, DEFAULT_START, DEFAULT_END) for wd in range(7)])
        self.conn.commit()
        return did

    def future_appointments(self, did):
        """Активные (не отменённые и не выполненные) записи врача начиная с сегодняшнего дня."""
        return self.conn.execute("""SELECT * FROM appointments WHERE doctor_id=? AND date>=?
                                    AND status IN ('Новая','Подтверждена') ORDER BY date,time""",
                                 (did, dt.date.today().isoformat())).fetchall()

    def delete_doctor(self, did):
        """Удаляет врача из справочника. Врач с активными записями не удаляется.
        Если у врача есть история приёмов, он переводится в архив, чтобы история и отчёты сохранились."""
        if not self.doctor(did):
            raise ValueError('Врач не найден')
        if self.future_appointments(did):
            raise ValueError('Нельзя удалить врача: у него есть активные записи на приём')
        self.conn.execute('DELETE FROM work_schedule WHERE doctor_id=?', (did,))
        has_history = self.conn.execute('SELECT 1 FROM appointments WHERE doctor_id=?', (did,)).fetchone()
        if has_history:
            self.conn.execute('UPDATE doctors SET active=0 WHERE id=?', (did,))
        else:
            self.conn.execute('DELETE FROM doctors WHERE id=?', (did,))
        self.conn.commit()

    # ===== График работы врачей (главный врач) =====
    def work_schedule(self, did):
        """Возвращает словарь {день недели: (начало, окончание)}; выходные дни отсутствуют."""
        rows = self.conn.execute('SELECT * FROM work_schedule WHERE doctor_id=?', (did,)).fetchall()
        return {r['weekday']: (r['start_time'], r['end_time']) for r in rows}

    def doctor_slots(self, did, date):
        """Слоты приёма врача на дату по его графику работы."""
        weekday = dt.date.fromisoformat(date).weekday()
        hours = self.work_schedule(did).get(weekday)
        return slots_for_hours(*hours) if hours else []

    def save_work_day(self, did, weekday, start=None, end=None):
        """Задаёт рабочие часы врача на день недели. start=None — выходной день.
        Изменение запрещено, если активные записи врача окажутся вне нового графика."""
        if not self.doctor(did):
            raise ValueError('Врач не найден')
        if weekday not in range(7):
            raise ValueError('Неверный день недели')
        allowed = []
        if start is not None:
            validate_work_hours(start, end)
            allowed = slots_for_hours(start, end)
        conflicts = [a for a in self.future_appointments(did)
                     if dt.date.fromisoformat(a['date']).weekday() == weekday and a['time'] not in allowed]
        if conflicts:
            first = conflicts[0]
            raise ValueError(f'Нельзя изменить график: есть активные записи вне нового времени приёма '
                             f'({len(conflicts)} шт., ближайшая {first["date"]} {first["time"]}). '
                             f'Сначала перенесите или отмените их')
        if start is None:
            self.conn.execute('DELETE FROM work_schedule WHERE doctor_id=? AND weekday=?', (did, weekday))
        else:
            self.conn.execute('''INSERT INTO work_schedule(doctor_id,weekday,start_time,end_time) VALUES(?,?,?,?)
                                 ON CONFLICT(doctor_id,weekday) DO UPDATE SET start_time=excluded.start_time,
                                 end_time=excluded.end_time''', (did, weekday, start, end))
        self.conn.commit()

    def stats(self, start, end):
        rows = self.appointments(start, end)
        active = [r for r in rows if r['status'] != 'Отменена']
        cancelled = [r for r in rows if r['status'] == 'Отменена']
        by_doctor = {}
        by_service = {}
        by_reason = {}
        for r in active:
            by_doctor[r['doctor_name']] = by_doctor.get(r['doctor_name'], 0) + 1
            by_service[r['service_name']] = by_service.get(r['service_name'], 0) + 1
        for r in cancelled:
            reason = r['cancel_reason'] or 'Причина не указана'
            by_reason[reason] = by_reason.get(reason, 0) + 1
        primary = 0
        for r in active:
            first = self.conn.execute(
                "SELECT MIN(date) first_date FROM appointments WHERE patient_id=? AND status!='Отменена'",
                (r['patient_id'],)).fetchone()['first_date']
            if first == r['date']:
                primary += 1
        return {'rows': rows, 'total': len(rows), 'active': len(active), 'cancelled': len(cancelled),
                'primary': primary, 'by_doctor': by_doctor, 'by_service': by_service, 'by_reason': by_reason}

    def quick_report(self, start, end, report_type):
        """Быстрый отчёт без оформления — возвращает список строк для отображения."""
        rows = self.appointments(start, end)
        active = [r for r in rows if r['status'] != 'Отменена']
        cancelled = [r for r in rows if r['status'] == 'Отменена']

        if report_type == 'total':
            return [
                'Отчёт по общему количеству записей',
                f'Период: {start} — {end}',
                f'Всего записей: {len(rows)}',
                f'Активных/завершённых: {len(active)}',
                f'Отменённых: {len(cancelled)}',
            ]
        if report_type == 'services':
            by_service = {}
            for r in active:
                by_service[r['service_name']] = by_service.get(r['service_name'], 0) + 1
            if not by_service:
                return ['Отчёт по услугам', f'Период: {start} — {end}', '',
                        'Нет данных за указанный период']
            lines = ['Отчёт по услугам', f'Период: {start} — {end}', '']
            for k, v in by_service.items():
                lines.append(f'  {k}: {v}')
            return lines
        if report_type == 'cancelled':
            by_reason = {}
            for r in cancelled:
                reason = r['cancel_reason'] or 'Причина не указана'
                by_reason[reason] = by_reason.get(reason, 0) + 1
            if not cancelled:
                return ['Отчёт по отменённым записям', f'Период: {start} — {end}', '',
                        'Нет данных за указанный период']
            lines = ['Отчёт по отменённым записям', f'Период: {start} — {end}', '',
                     f'Всего отменено: {len(cancelled)}', '']
            for k, v in by_reason.items():
                lines.append(f'  {k}: {v}')
            return lines
        return ['Неизвестный тип отчёта']


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('АРМ стоматологической клиники «Ассоль»')
        self.geometry('1280x780')
        self.minsize(1050, 650)
        self.db = Database()
        self.user = None
        self.current_page = None
        self.configure(bg='#f4f6f8')
        self.show_login()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def style(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('TButton', font=('Segoe UI', 10), padding=(12, 7))
        s.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=(14, 8))
        s.configure('TLabel', font=('Segoe UI', 10))
        s.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        s.configure('Sub.TLabel', font=('Segoe UI', 11))
        s.configure('Treeview', font=('Segoe UI', 10), rowheight=30)
        s.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        s.configure('TEntry', padding=6)
        s.configure('TCombobox', padding=5)

    def show_login(self):
        self.clear()
        self.style()
        outer = ttk.Frame(self, padding=30)
        outer.place(relx=.5, rely=.5, anchor='center')
        ttk.Label(outer, text='АРМ клиники «Ассоль»', style='Title.TLabel').grid(row=0, column=0, columnspan=2, pady=(0, 5))
        ttk.Label(outer, text='Вход администратора и главного врача', style='Sub.TLabel').grid(row=1, column=0, columnspan=2, pady=(0, 25))
        ttk.Label(outer, text='Логин').grid(row=2, column=0, sticky='w', pady=7)
        login = ttk.Entry(outer, width=30)
        login.grid(row=2, column=1, pady=7)
        ttk.Label(outer, text='Пароль').grid(row=3, column=0, sticky='w', pady=7)
        password = ttk.Entry(outer, width=30, show='•')
        password.grid(row=3, column=1, pady=7)
        ttk.Button(outer, text='Войти', style='Primary.TButton',
                   command=lambda: self.login(login.get(), password.get())).grid(row=4, column=0, columnspan=2, pady=18, sticky='ew')
        ttk.Label(outer, text='Демонстрационные учётные записи:').grid(row=5, column=0, columnspan=2, pady=(5, 0))
        ttk.Label(outer, text='администратор — admin / admin,  главный врач — chief / chief').grid(
            row=6, column=0, columnspan=2, pady=(0, 5))
        password.bind('<Return>', lambda e: self.login(login.get(), password.get()))
        login.focus_set()

    def login(self, login, password):
        u = self.db.authenticate(login, password)
        if not u:
            messagebox.showerror('Ошибка входа', 'Неправильный логин или пароль')
            return
        self.user = u
        self.show_main()

    def show_main(self):
        self.clear()
        self.style()
        top = tk.Frame(self, bg='#26364a', height=64)
        top.pack(fill='x')
        top.pack_propagate(False)
        tk.Label(top, text='АРМ «Ассоль»', bg='#26364a', fg='white', font=('Segoe UI', 16, 'bold')).pack(side='left', padx=22)
        role_name = ROLE_NAMES.get(self.user['role'], self.user['role'])
        tk.Label(top, text=f"{self.user['full_name']} ({role_name})", bg='#26364a', fg='#dbe5ef',
                 font=('Segoe UI', 10)).pack(side='right', padx=18)
        body = tk.Frame(self, bg='#f4f6f8')
        body.pack(fill='both', expand=True)
        nav = tk.Frame(body, bg='#e9edf2', width=210)
        nav.pack(side='left', fill='y')
        nav.pack_propagate(False)
        content = tk.Frame(body, bg='#f4f6f8')
        content.pack(side='left', fill='both', expand=True)
        self.content = content
        self.nav_buttons = {}
        for text, fn in self.nav_items():
            b = tk.Button(nav, text=text, command=fn, anchor='w', relief='flat', bd=0, bg='#e9edf2',
                          activebackground='#d9e0e8', font=('Segoe UI', 10), padx=22, pady=13)
            b.pack(fill='x')
            self.nav_buttons[text] = b
        tk.Frame(nav, bg='#cbd3dc', height=1).pack(fill='x', padx=15, pady=10)
        tk.Button(nav, text='Выйти', command=self.show_login, anchor='w', relief='flat', bd=0,
                  bg='#e9edf2', font=('Segoe UI', 10), padx=22, pady=13).pack(fill='x')
        if self.is_chief():
            self.page_doctors()
        else:
            self.page_schedule()

    def is_chief(self):
        return self.user is not None and self.user['role'] == 'chief'

    def nav_items(self):
        """Разделы меню в зависимости от роли.
        Главный врач работает только с разделами администрирования, администратор — с записью пациентов."""
        if self.is_chief():
            return [('Врачи', self.page_doctors), ('График работы', self.page_work_schedule),
                    ('Учётные записи', self.page_accounts)]
        return [('Расписание', self.page_schedule), ('Запись на приём', self.page_appointment),
                ('Поиск пациента', self.page_patients), ('Врачи', self.page_doctors),
                ('Отчётность', self.page_reports)]

    def page_frame(self, title, subtitle=''):
        for w in self.content.winfo_children():
            w.destroy()
        f = ttk.Frame(self.content, padding=22)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=title, style='Title.TLabel').pack(anchor='w')
        if subtitle:
            ttk.Label(f, text=subtitle, style='Sub.TLabel').pack(anchor='w', pady=(4, 18))
        else:
            ttk.Frame(f, height=16).pack()
        return f

    def prepare_dialog(self, win, width, height):
        win.minsize(width, height)
        win.geometry(f'{width}x{height}')
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        win.geometry(f'{width}x{height}+{x}+{y}')

    def tree(self, parent, cols, widths):
        wrap = ttk.Frame(parent)
        wrap.pack(fill='both', expand=True)
        tv = ttk.Treeview(wrap, columns=cols, show='headings')
        for c, w in zip(cols, widths):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor='w')
        ys = ttk.Scrollbar(wrap, orient='vertical', command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side='left', fill='both', expand=True)
        ys.pack(side='right', fill='y')
        return tv

    def page_schedule(self):
        f = self.page_frame('Расписание', 'Свободные и занятые временные слоты на ближайшие 14 календарных дней.')
        bar = ttk.Frame(f)
        bar.pack(fill='x', pady=(0, 14))
        ttk.Label(bar, text='Врач:').pack(side='left')
        doctors = self.db.doctors()
        dvar = tk.StringVar(value=doctors[0]['full_name'] if doctors else '')
        dmap = {r['full_name']: r['id'] for r in doctors}
        dc = ttk.Combobox(bar, textvariable=dvar, values=list(dmap), state='readonly', width=32)
        dc.pack(side='left', padx=7)
        ttk.Label(bar, text='Дата:').pack(side='left', padx=(18, 4))
        datevar = tk.StringVar(value=dt.date.today().isoformat())
        de = ttk.Entry(bar, textvariable=datevar, width=13)
        de.pack(side='left')
        tv = self.tree(f, ['Дата', 'Время', 'Статус', 'Пациент', 'Услуга', 'Статус записи'],
                       [110, 80, 90, 230, 240, 130])

        def load():
            for x in tv.get_children():
                tv.delete(x)
            try:
                selected_date = dt.date.fromisoformat(datevar.get())
            except ValueError:
                messagebox.showerror('Ошибка', 'Введите дату в формате ГГГГ-ММ-ДД')
                return
            today = dt.date.today()
            last_date = today + dt.timedelta(days=13)
            if selected_date < today:
                messagebox.showerror('Ошибка', 'Нельзя открыть запись на прошедшую дату. Выберите сегодня или будущую дату.')
                return
            if selected_date > last_date:
                messagebox.showerror('Ошибка', 'Расписание доступно только на ближайшие 14 календарных дней.')
                return
            date = selected_date.isoformat()
            did = dmap.get(dvar.get())
            rows = self.db.appointments(date, date, doctor_id=did)
            work_slots = self.db.doctor_slots(did, date) if did else []
            for t in SLOT_TIMES:
                r = next((x for x in rows if x['time'] == t and x['status'] != 'Отменена'), None)
                if not r and t not in work_slots:
                    tv.insert('', 'end', values=(date, t, 'Нет приёма', '', '', ''), tags=('past',))
                elif r:
                    tv.insert('', 'end', values=(date, t, 'Занят', r['patient_name'], r['service_name'], r['status']),
                              tags=(str(r['id']),))
                else:
                    slot_dt = dt.datetime.combine(selected_date, dt.datetime.strptime(t, '%H:%M').time())
                    if slot_dt <= dt.datetime.now():
                        tv.insert('', 'end', values=(date, t, 'Недоступен', '', '', ''), tags=('past',))
                    else:
                        tv.insert('', 'end', values=(date, t, 'Свободен', '', '', ''), tags=('free',))
            tv.tag_configure('free', foreground='#18794e')
            tv.tag_configure('past', foreground='#888888')

        ttk.Button(bar, text='Показать расписание', command=load).pack(side='left', padx=12)

        def open_slot(event=None):
            sel = tv.selection()
            if not sel:
                return
            vals = tv.item(sel[0], 'values')
            if vals[2] == 'Свободен':
                self.open_appointment_dialog(date=vals[0], time=vals[1], doctor_id=dmap.get(dvar.get()))
            elif vals[2] == 'Занят':
                aid = tv.item(sel[0], 'tags')[0]
                self.open_appointment_dialog(appointment_id=int(aid))

        tv.bind('<Double-1>', open_slot)
        load()

    def page_appointment(self):
        self.open_appointment_dialog()

    def open_appointment_dialog(self, appointment_id=None, date=None, time=None, doctor_id=None):
        win = tk.Toplevel(self)
        win.title('Запись на приём')
        self.prepare_dialog(win, 820, 720)
        win.transient(self)
        win.grab_set()
        outer = ttk.Frame(win, padding=22)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Оформление записи на приём', style='Title.TLabel').pack(anchor='w', pady=(0, 15))
        ap = None
        if appointment_id:
            ap = self.db.appointments(doctor_id=None, include_cancelled=True)
            ap = next((r for r in ap if r['id'] == appointment_id), None)
        services = self.db.services()
        s_names = [f"{r['name']} — {r['category']}" for r in services]
        s_map = {f"{r['name']} — {r['category']}": r['id'] for r in services}
        if ap:
            date = ap['date']
            time = ap['time']
            doctor_id = ap['doctor_id']

        row = ttk.Frame(outer)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text='Поиск пациента').pack(side='left')
        q = tk.StringVar()
        qe = ttk.Entry(row, textvariable=q, width=35)
        qe.pack(side='left', padx=8)
        result = tk.Listbox(outer, height=4)
        result.pack(fill='x', pady=4)
        selected_patient = [ap['patient_id'] if ap else None]

        def search():
            result.delete(0, 'end')
            for p in self.db.search_patients(q.get()):
                result.insert('end', f"{p['id']} | {p['full_name']} | {p['phone']} | {p['passport']}")

        ttk.Button(row, text='Найти', command=search).pack(side='left')
        fields = ttk.Frame(outer)
        fields.pack(fill='x', pady=5)
        full = tk.StringVar(value=ap['patient_name'] if ap else '')
        birth = tk.StringVar(value=self.db.patient(ap['patient_id'])['birth_date'] if ap else '')
        phone = tk.StringVar(value=ap['phone'] if ap else '')
        passport = tk.StringVar(value=self.db.patient(ap['patient_id'])['passport'] if ap else '')
        notif = tk.StringVar(value=self.db.patient(ap['patient_id'])['notification'] if ap else 'SMS-сообщение')

        def add_field(label, var, r):
            ttk.Label(fields, text=label).grid(row=r, column=0, sticky='w', pady=4)
            ttk.Entry(fields, textvariable=var, width=43).grid(row=r, column=1, sticky='w', pady=4)

        add_field('ФИО пациента *', full, 0)
        add_field('Дата рождения *', birth, 1)
        add_field('Телефон *', phone, 2)
        add_field('Номер паспорта *', passport, 3)
        ttk.Label(fields, text='Уведомление').grid(row=4, column=0, sticky='w', pady=4)
        ttk.Combobox(fields, textvariable=notif, values=['SMS-сообщение', 'Обратный звонок'],
                     state='readonly', width=40).grid(row=4, column=1, sticky='w', pady=4)
        result.bind('<<ListboxSelect>>',
                    lambda e: self.select_patient(result, full, birth, phone, passport, notif, selected_patient))
        ttk.Label(outer, text='Параметры приёма', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(15, 5))
        params = ttk.Frame(outer)
        params.pack(fill='x')
        ttk.Label(params, text='Услуга *').grid(row=0, column=0, sticky='w', pady=5)
        sv = tk.StringVar(value=(next((f"{r['name']} — {r['category']}" for r in services if r['id'] == ap['service_id']),
                                     s_names[0]) if ap else s_names[0]))
        sc = ttk.Combobox(params, textvariable=sv, values=s_names, state='readonly', width=40)
        sc.grid(row=0, column=1, sticky='w', pady=5)
        ttk.Label(params, text='Врач *').grid(row=1, column=0, sticky='w', pady=5)
        dv = tk.StringVar()
        dc = ttk.Combobox(params, textvariable=dv, state='readonly', width=40)
        dc.grid(row=1, column=1, sticky='w', pady=5)
        ttk.Label(params, text='Дата *').grid(row=2, column=0, sticky='w', pady=5)
        datev = tk.StringVar(value=date or dt.date.today().isoformat())
        ttk.Entry(params, textvariable=datev, width=43).grid(row=2, column=1, sticky='w', pady=5)
        ttk.Label(params, text='Время *').grid(row=3, column=0, sticky='w', pady=5)
        tv = tk.StringVar(value=time or SLOT_TIMES[0])
        ttk.Combobox(params, textvariable=tv, values=SLOT_TIMES, state='readonly', width=40).grid(row=3, column=1, sticky='w', pady=5)

        def load_doctors():
            chosen = s_map.get(sv.get())
            ds = self.db.doctors_for_service(chosen)
            names = [d['full_name'] for d in ds]
            dc['values'] = names
            wanted = next((d['full_name'] for d in ds if d['id'] == doctor_id), names[0] if names else '')
            dv.set(wanted)

        sc.bind('<<ComboboxSelected>>', lambda e: load_doctors())
        load_doctors()
        btn = ttk.Frame(outer)
        btn.pack(fill='x', pady=18)

        def save():
            try:
                if not full.get().strip() or not birth.get().strip() or not phone.get().strip() or not passport.get().strip():
                    raise ValueError('Заполните все поля пациента')
                validate_appointment_datetime(datev.get(), tv.get())
                p = selected_patient[0]
                if not p:
                    p = self.db.save_patient({'full_name': full.get().strip(), 'birth_date': birth.get().strip(),
                                              'phone': phone.get().strip(), 'passport': passport.get().strip(),
                                              'notification': notif.get()})
                else:
                    self.db.save_patient({'id': p, 'full_name': full.get().strip(), 'birth_date': birth.get().strip(),
                                          'phone': phone.get().strip(), 'passport': passport.get().strip(),
                                          'notification': notif.get()})
                did = next(d['id'] for d in self.db.doctors(include_inactive=True) if d['full_name'] == dv.get())
                sid = s_map[sv.get()]
                if appointment_id:
                    self.db.update_appointment(appointment_id, p, did, sid, datev.get(), tv.get())
                else:
                    self.db.create_appointment(p, did, sid, datev.get(), tv.get())
                messagebox.showinfo('Готово', 'Запись успешно сохранена', parent=win)
                win.destroy()
                self.page_schedule()
            except sqlite3.IntegrityError:
                messagebox.showerror('Ошибка', 'Пациент с таким номером телефона уже существует', parent=win)
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e), parent=win)

        ttk.Button(btn, text='Сохранить запись', style='Primary.TButton', command=save).pack(side='left')
        if appointment_id:
            ttk.Button(btn, text='Отменить запись',
                       command=lambda: self.cancel_from_dialog(appointment_id, win)).pack(side='left', padx=8)
            ttk.Button(btn, text='Отметить выполненной',
                       command=lambda: self.complete_from_dialog(appointment_id, win)).pack(side='left')
        ttk.Button(btn, text='Закрыть', command=win.destroy).pack(side='right')

    def select_patient(self, result, full, birth, phone, passport, notif, target):
        if not result.curselection():
            return
        pid = int(result.get(result.curselection()[0]).split('|')[0].strip())
        p = self.db.patient(pid)
        target[0] = pid
        full.set(p['full_name'])
        birth.set(p['birth_date'])
        phone.set(p['phone'])
        passport.set(p['passport'])
        notif.set(p['notification'])

    def cancel_from_dialog(self, aid, win):
        reason = tk.simpledialog.askstring('Причина отмены', 'Укажите причину (необязательно):', parent=win)
        if messagebox.askyesno('Подтверждение', 'Отменить запись?', parent=win):
            try:
                self.db.cancel(aid, reason)
                messagebox.showinfo('Готово', 'Запись успешно отменена', parent=win)
                win.destroy()
                self.page_schedule()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e), parent=win)

    def complete_from_dialog(self, aid, win):
        self.db.complete(aid)
        messagebox.showinfo('Готово', 'Запись отмечена как выполненная', parent=win)
        win.destroy()
        self.page_schedule()

    def page_patients(self):
        f = self.page_frame('Поиск пациента', 'Поиск по фамилии полностью или частично, телефону или номеру паспорта.')
        bar = ttk.Frame(f)
        bar.pack(fill='x', pady=(0, 12))
        q = tk.StringVar()
        ttk.Entry(bar, textvariable=q, width=45).pack(side='left')
        tv = self.tree(f, ['ID', 'ФИО', 'Дата рождения', 'Телефон', 'Паспорт', 'Уведомление'],
                       [60, 250, 130, 170, 150, 170])

        def load():
            for x in tv.get_children():
                tv.delete(x)
            for p in self.db.search_patients(q.get()):
                tv.insert('', 'end', values=(p['id'], p['full_name'], p['birth_date'], p['phone'], p['passport'],
                                             p['notification']))

        ttk.Button(bar, text='Найти', command=load).pack(side='left', padx=8)
        ttk.Button(bar, text='Новый пациент', command=lambda: self.patient_dialog()).pack(side='left')

        def card():
            s = tv.selection()
            if not s:
                return
            self.patient_dialog(int(tv.item(s[0], 'values')[0]))

        ttk.Button(bar, text='Карточка пациента', command=card).pack(side='left', padx=8)
        ttk.Button(bar, text='Записать на приём', command=lambda: self.open_appointment_dialog()).pack(side='left')
        tv.bind('<Double-1>', lambda e: card())
        load()

    def patient_dialog(self, pid=None):
        p = self.db.patient(pid) if pid else None
        w = tk.Toplevel(self)
        w.title('Карточка пациента')
        self.prepare_dialog(w, 850, 780)
        w.transient(self)
        w.grab_set()
        f = ttk.Frame(w, padding=20)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Карточка пациента', style='Title.TLabel').pack(anchor='w', pady=(0, 12))
        form = ttk.Frame(f)
        form.pack(fill='x')
        vals = {k: tk.StringVar(value=p[k] if p else '') for k in
                ['full_name', 'birth_date', 'phone', 'passport', 'notification']}
        labels = {'full_name': 'ФИО *', 'birth_date': 'Дата рождения *', 'phone': 'Телефон *',
                  'passport': 'Номер паспорта *', 'notification': 'Уведомление'}
        for i, k in enumerate(vals):
            ttk.Label(form, text=labels[k]).grid(row=i, column=0, sticky='w', pady=5)
            (ttk.Combobox(form, textvariable=vals[k], values=['SMS-сообщение', 'Обратный звонок'],
                          state='readonly', width=43) if k == 'notification'
             else ttk.Entry(form, textvariable=vals[k], width=46)).grid(row=i, column=1, sticky='w', pady=5)
        if not p:
            vals['notification'].set('SMS-сообщение')
        ttk.Label(f, text='История записей', font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(18, 5))
        tv = self.tree(f, ['Дата', 'Время', 'Врач', 'Услуга', 'Статус'], [110, 80, 230, 220, 120])
        if p:
            for a in self.db.appointments(patient_id=pid):
                tv.insert('', 'end', values=(a['date'], a['time'], a['doctor_name'], a['service_name'], a['status']))

        def save():
            try:
                if any(not vals[k].get().strip() for k in ['full_name', 'birth_date', 'phone', 'passport']):
                    raise ValueError('Заполните все обязательные поля')
                dt.date.fromisoformat(vals['birth_date'].get())
                self.db.save_patient({'id': pid, 'full_name': vals['full_name'].get(),
                                      'birth_date': vals['birth_date'].get(), 'phone': vals['phone'].get(),
                                      'passport': vals['passport'].get(), 'notification': vals['notification'].get()})
                w.destroy()
                self.page_patients()
            except Exception as e:
                messagebox.showerror('Ошибка', str(e), parent=w)

        ttk.Button(f, text='Сохранить', style='Primary.TButton', command=save).pack(side='left', pady=15)
        ttk.Button(f, text='Закрыть', command=w.destroy).pack(side='right', pady=15)

    def page_doctors(self):
        if not self.is_chief():
            f = self.page_frame('Справочник врачей', 'Данные врачей доступны администратору только для просмотра.')
            tv = self.tree(f, ['ФИО', 'Специализация', 'Стаж, лет', 'Квалификация'], [330, 250, 100, 300])
            for d in self.db.doctors():
                tv.insert('', 'end', values=(d['full_name'], d['specialization'], d['experience'], d['qualification']))
            return
        f = self.page_frame('Справочник врачей', 'Добавление, изменение и удаление врачей клиники.')
        bar = ttk.Frame(f)
        bar.pack(fill='x', pady=(0, 12))
        tv = self.tree(f, ['ID', 'ФИО', 'Специализация', 'Стаж, лет', 'Квалификация'], [60, 300, 230, 100, 260])

        def load():
            for x in tv.get_children():
                tv.delete(x)
            for d in self.db.doctors():
                tv.insert('', 'end', values=(d['id'], d['full_name'], d['specialization'], d['experience'],
                                             d['qualification']))

        def selected_id():
            s = tv.selection()
            if not s:
                messagebox.showinfo('Справочник врачей', 'Выберите врача в списке')
                return None
            return int(tv.item(s[0], 'values')[0])

        def edit():
            did = selected_id()
            if did:
                self.doctor_dialog(did, on_save=load)

        def delete():
            did = selected_id()
            if not did:
                return
            d = self.db.doctor(did)
            if not messagebox.askyesno('Подтверждение', f'Удалить врача «{d["full_name"]}» из справочника?'):
                return
            try:
                self.db.delete_doctor(did)
                messagebox.showinfo('Готово', 'Врач удалён из справочника')
                load()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        ttk.Button(bar, text='Добавить врача', style='Primary.TButton',
                   command=lambda: self.doctor_dialog(on_save=load)).pack(side='left')
        ttk.Button(bar, text='Изменить', command=edit).pack(side='left', padx=8)
        ttk.Button(bar, text='Удалить', command=delete).pack(side='left')
        tv.bind('<Double-1>', lambda e: edit())
        load()

    def doctor_dialog(self, did=None, on_save=None):
        d = self.db.doctor(did) if did else None
        w = tk.Toplevel(self)
        w.title('Карточка врача')
        self.prepare_dialog(w, 640, 380)
        w.transient(self)
        w.grab_set()
        f = ttk.Frame(w, padding=22)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Изменение данных врача' if d else 'Новый врач', style='Title.TLabel').grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 15))
        name = tk.StringVar(value=d['full_name'] if d else '')
        spec = tk.StringVar(value=d['specialization'] if d else SPECIALIZATIONS[0])
        exp = tk.StringVar(value=str(d['experience']) if d else '')
        qual = tk.StringVar(value=d['qualification'] if d else QUALIFICATIONS[0])
        ttk.Label(f, text='ФИО *').grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(f, textvariable=name, width=44).grid(row=1, column=1, sticky='w', pady=5)
        ttk.Label(f, text='Специализация *').grid(row=2, column=0, sticky='w', pady=5)
        ttk.Combobox(f, textvariable=spec, values=SPECIALIZATIONS, state='readonly', width=41).grid(
            row=2, column=1, sticky='w', pady=5)
        ttk.Label(f, text='Стаж, лет *').grid(row=3, column=0, sticky='w', pady=5)
        ttk.Entry(f, textvariable=exp, width=44).grid(row=3, column=1, sticky='w', pady=5)
        ttk.Label(f, text='Квалификация *').grid(row=4, column=0, sticky='w', pady=5)
        ttk.Combobox(f, textvariable=qual, values=QUALIFICATIONS, state='readonly', width=41).grid(
            row=4, column=1, sticky='w', pady=5)

        def save():
            try:
                self.db.save_doctor({'id': did, 'full_name': name.get(), 'specialization': spec.get(),
                                              'experience': exp.get(), 'qualification': qual.get()})
                messagebox.showinfo('Готово', 'Данные врача сохранены', parent=w)
                w.destroy()
                if on_save:
                    on_save()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e), parent=w)

        btn = ttk.Frame(f)
        btn.grid(row=5, column=0, columnspan=2, sticky='ew', pady=20)
        ttk.Button(btn, text='Сохранить', style='Primary.TButton', command=save).pack(side='left')
        ttk.Button(btn, text='Закрыть', command=w.destroy).pack(side='right')

    def page_work_schedule(self):
        f = self.page_frame('График работы врачей',
                            'Рабочие дни и часы приёма. По графику администратор видит свободные слоты в расписании.')
        bar = ttk.Frame(f)
        bar.pack(fill='x', pady=(0, 14))
        ttk.Label(bar, text='Врач:').pack(side='left')
        doctors = self.db.doctors()
        dmap = {r['full_name']: r['id'] for r in doctors}
        dvar = tk.StringVar(value=doctors[0]['full_name'] if doctors else '')
        dc = ttk.Combobox(bar, textvariable=dvar, values=list(dmap), state='readonly', width=34)
        dc.pack(side='left', padx=7)
        tv = self.tree(f, ['День недели', 'Режим', 'Начало приёма', 'Окончание приёма', 'Слотов приёма'],
                       [180, 130, 150, 160, 140])

        def load():
            for x in tv.get_children():
                tv.delete(x)
            did = dmap.get(dvar.get())
            if not did:
                return
            sched = self.db.work_schedule(did)
            for wd, day in enumerate(WEEKDAYS):
                if wd in sched:
                    start, end = sched[wd]
                    tv.insert('', 'end', iid=str(wd),
                              values=(day, 'Рабочий', start, end, len(slots_for_hours(start, end))))
                else:
                    tv.insert('', 'end', iid=str(wd), values=(day, 'Выходной', '—', '—', 0), tags=('off',))
            tv.tag_configure('off', foreground='#888888')

        def edit_day():
            s = tv.selection()
            did = dmap.get(dvar.get())
            if not s or not did:
                messagebox.showinfo('График работы', 'Выберите день недели в таблице')
                return
            self.work_day_dialog(did, int(s[0]), on_save=load)

        dc.bind('<<ComboboxSelected>>', lambda e: load())
        ttk.Button(bar, text='Изменить день', style='Primary.TButton', command=edit_day).pack(side='left', padx=12)
        tv.bind('<Double-1>', lambda e: edit_day())
        load()

    def work_day_dialog(self, did, weekday, on_save=None):
        hours = self.db.work_schedule(did).get(weekday)
        w = tk.Toplevel(self)
        w.title('График работы')
        self.prepare_dialog(w, 560, 330)
        w.transient(self)
        w.grab_set()
        f = ttk.Frame(w, padding=22)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=WEEKDAYS[weekday], style='Title.TLabel').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(f, text=self.db.doctor(did)['full_name'], style='Sub.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(2, 14))
        working = tk.BooleanVar(value=hours is not None)
        start = tk.StringVar(value=hours[0] if hours else DEFAULT_START)
        end = tk.StringVar(value=hours[1] if hours else DEFAULT_END)
        ttk.Checkbutton(f, text='Рабочий день', variable=working).grid(row=2, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(f, text='Начало приёма').grid(row=3, column=0, sticky='w', pady=5)
        ttk.Combobox(f, textvariable=start, values=WORK_TIMES, state='readonly', width=12).grid(
            row=3, column=1, sticky='w', pady=5)
        ttk.Label(f, text='Окончание приёма').grid(row=4, column=0, sticky='w', pady=5)
        ttk.Combobox(f, textvariable=end, values=WORK_TIMES, state='readonly', width=12).grid(
            row=4, column=1, sticky='w', pady=5)

        def save():
            try:
                if working.get():
                    self.db.save_work_day(did, weekday, start.get(), end.get())
                else:
                    self.db.save_work_day(did, weekday)
                messagebox.showinfo('Готово', 'График работы сохранён', parent=w)
                w.destroy()
                if on_save:
                    on_save()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e), parent=w)

        btn = ttk.Frame(f)
        btn.grid(row=5, column=0, columnspan=2, sticky='ew', pady=20)
        ttk.Button(btn, text='Сохранить', style='Primary.TButton', command=save).pack(side='left')
        ttk.Button(btn, text='Закрыть', command=w.destroy).pack(side='left', padx=8)

    def page_accounts(self):
        f = self.page_frame('Учётные записи администраторов',
                            'Создание, изменение, блокировка и удаление учётных записей администраторов клиники.')
        bar = ttk.Frame(f)
        bar.pack(fill='x', pady=(0, 12))
        tv = self.tree(f, ['ID', 'ФИО', 'Логин', 'Роль', 'Статус'], [60, 320, 180, 160, 140])

        def load():
            for x in tv.get_children():
                tv.delete(x)
            for a in self.db.accounts():
                status = 'Активна' if a['active'] else 'Заблокирована'
                tv.insert('', 'end', values=(a['id'], a['full_name'], a['login'], ROLE_NAMES[a['role']], status),
                          tags=() if a['active'] else ('blocked',))
            tv.tag_configure('blocked', foreground='#b42318')

        def selected_id():
            s = tv.selection()
            if not s:
                messagebox.showinfo('Учётные записи', 'Выберите учётную запись в списке')
                return None
            return int(tv.item(s[0], 'values')[0])

        def edit():
            aid = selected_id()
            if aid:
                self.account_dialog(aid, on_save=load)

        def change_password():
            aid = selected_id()
            if not aid:
                return
            pwd = simpledialog.askstring('Смена пароля', 'Новый пароль (не менее 6 символов, буквы и цифры):',
                                         show='•', parent=self)
            if pwd is None:
                return
            try:
                self.db.change_password(aid, pwd)
                messagebox.showinfo('Готово', 'Пароль изменён')
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        def toggle_block():
            aid = selected_id()
            if not aid:
                return
            a = self.db.account(aid)
            action = 'Разблокировать' if not a['active'] else 'Заблокировать'
            if not messagebox.askyesno('Подтверждение', f'{action} учётную запись «{a["login"]}»?'):
                return
            try:
                self.db.set_account_active(aid, not a['active'])
                load()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        def delete():
            aid = selected_id()
            if not aid:
                return
            a = self.db.account(aid)
            if not messagebox.askyesno('Подтверждение', f'Удалить учётную запись «{a["login"]}»? Действие необратимо.'):
                return
            try:
                self.db.delete_account(aid)
                messagebox.showinfo('Готово', 'Учётная запись удалена')
                load()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        ttk.Button(bar, text='Новая учётная запись', style='Primary.TButton',
                   command=lambda: self.account_dialog(on_save=load)).pack(side='left')
        ttk.Button(bar, text='Изменить', command=edit).pack(side='left', padx=8)
        ttk.Button(bar, text='Сменить пароль', command=change_password).pack(side='left')
        ttk.Button(bar, text='Заблокировать / разблокировать', command=toggle_block).pack(side='left', padx=8)
        ttk.Button(bar, text='Удалить', command=delete).pack(side='left')
        tv.bind('<Double-1>', lambda e: edit())
        load()

    def account_dialog(self, aid=None, on_save=None):
        a = self.db.account(aid) if aid else None
        w = tk.Toplevel(self)
        w.title('Учётная запись')
        self.prepare_dialog(w, 620, 360)
        w.transient(self)
        w.grab_set()
        f = ttk.Frame(w, padding=22)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text='Изменение учётной записи' if a else 'Новая учётная запись', style='Title.TLabel').grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 15))
        name = tk.StringVar(value=a['full_name'] if a else '')
        login = tk.StringVar(value=a['login'] if a else '')
        pwd = tk.StringVar()
        ttk.Label(f, text='ФИО сотрудника *').grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(f, textvariable=name, width=40).grid(row=1, column=1, sticky='w', pady=5)
        ttk.Label(f, text='Логин *').grid(row=2, column=0, sticky='w', pady=5)
        ttk.Entry(f, textvariable=login, width=40).grid(row=2, column=1, sticky='w', pady=5)
        if not a:
            ttk.Label(f, text='Пароль *').grid(row=3, column=0, sticky='w', pady=5)
            ttk.Entry(f, textvariable=pwd, width=40, show='•').grid(row=3, column=1, sticky='w', pady=5)
        ttk.Label(f, text='Роль: Администратор').grid(row=4, column=0, columnspan=2, sticky='w', pady=5)

        def save():
            try:
                self.db.save_account({'id': aid, 'full_name': name.get(), 'login': login.get(), 'password': pwd.get()})
                messagebox.showinfo('Готово', 'Учётная запись сохранена', parent=w)
                w.destroy()
                if on_save:
                    on_save()
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e), parent=w)

        btn = ttk.Frame(f)
        btn.grid(row=5, column=0, columnspan=2, sticky='ew', pady=18)
        ttk.Button(btn, text='Сохранить', style='Primary.TButton', command=save).pack(side='left')
        ttk.Button(btn, text='Закрыть', command=w.destroy).pack(side='right')

    def page_reports(self):
        f = self.page_frame('Отчётность', 'Быстрые отчёты (без оформления) и сводный отчёт с экспортом в Excel/PDF.')
        bar = ttk.Frame(f)
        bar.pack(fill='x', pady=(0, 12))
        ttk.Label(bar, text='С:').pack(side='left')
        sv = tk.StringVar(value=dt.date.today().replace(day=1).isoformat())
        ttk.Entry(bar, textvariable=sv, width=13).pack(side='left', padx=5)
        ttk.Label(bar, text='По:').pack(side='left')
        ev = tk.StringVar(value=dt.date.today().isoformat())
        ttk.Entry(bar, textvariable=ev, width=13).pack(side='left', padx=5)

        # ===== Быстрые отчёты =====
        quick_bar = ttk.LabelFrame(f, text='Быстрые отчёты (без оформления, не сохраняются)', padding=10)
        quick_bar.pack(fill='x', pady=(0, 12))

        out = ttk.Frame(f)
        out.pack(fill='both', expand=True)
        text = tk.Text(out, font=('Consolas', 10), wrap='word', state='disabled', bg='white', relief='flat')
        text.pack(fill='both', expand=True)

        last = [None]

        def show_lines(lines):
            text.configure(state='normal')
            text.delete('1.0', 'end')
            text.insert('1.0', '\n'.join(lines))
            text.configure(state='disabled')

        def get_period():
            start = dt.date.fromisoformat(sv.get()).isoformat()
            end = dt.date.fromisoformat(ev.get()).isoformat()
            if start > end:
                raise ValueError('Дата начала не может быть позже даты окончания')
            return start, end

        def quick_total():
            try:
                start, end = get_period()
                show_lines(self.db.quick_report(start, end, 'total'))
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        def quick_services():
            try:
                start, end = get_period()
                show_lines(self.db.quick_report(start, end, 'services'))
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        def quick_cancelled():
            try:
                start, end = get_period()
                show_lines(self.db.quick_report(start, end, 'cancelled'))
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        ttk.Button(quick_bar, text='Отчёт по количеству записей', command=quick_total).pack(side='left', padx=4)
        ttk.Button(quick_bar, text='Отчёт по услугам', command=quick_services).pack(side='left', padx=4)
        ttk.Button(quick_bar, text='Отчёт по отменам', command=quick_cancelled).pack(side='left', padx=4)

        # ===== Сводный отчёт =====
        summary_bar = ttk.LabelFrame(f, text='Сводный отчёт (оформленный, с экспортом)', padding=10)
        summary_bar.pack(fill='x', pady=(0, 12))

        def generate():
            try:
                start, end = get_period()
                st = self.db.stats(start, end)
                last[0] = st
                if not st['rows']:
                    messagebox.showinfo('Отчёт', 'Нет данных за указанный период')
                    last[0] = None
                    return
                lines = [
                    'СВОДНЫЙ ОТЧЁТ КЛИНИКИ «АССОЛЬ»',
                    f'Период: {start} — {end}', '',
                    f'Общее количество записей: {st["total"]}',
                    f'Активных/завершённых: {st["active"]}',
                    f'Отменённых: {st["cancelled"]}',
                    f'Первичных обращений: {st["primary"]}', '',
                    'ЗАПИСИ ПО ВРАЧАМ:'
                ]
                lines += [f'  {k}: {v}' for k, v in st['by_doctor'].items()]
                lines += ['', 'ЗАПИСИ ПО УСЛУГАМ:']
                lines += [f'  {k}: {v}' for k, v in st['by_service'].items()]
                lines += ['', 'ОТМЕНЫ ПО ПРИЧИНАМ:']
                lines += [f'  {k}: {v}' for k, v in st['by_reason'].items()]
                show_lines(lines)
            except ValueError as e:
                messagebox.showerror('Ошибка', str(e))

        def export_excel():
            if not last[0]:
                messagebox.showinfo('Экспорт', 'Нет данных для экспорта. Сначала сформируйте сводный отчёт.')
                return
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font
            except ImportError:
                messagebox.showerror('Экспорт', 'Для Excel установите пакет openpyxl')
                return
            path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')],
                                                initialfile='otchet_assol.xlsx')
            if not path:
                return
            st = last[0]
            wb = Workbook()
            ws = wb.active
            ws.title = 'Сводный отчёт'
            ws.append(['Показатель', 'Значение'])
            for k, v in [('Общее количество записей', st['total']), ('Активных/завершённых', st['active']),
                         ('Отменённых', st['cancelled']), ('Первичных обращений', st['primary'])]:
                ws.append([k, v])
            ws.append([])
            ws.append(['Врач', 'Количество записей'])
            for k, v in st['by_doctor'].items():
                ws.append([k, v])
            ws.append([])
            ws.append(['Услуга', 'Количество записей'])
            for k, v in st['by_service'].items():
                ws.append([k, v])
            ws.append([])
            ws.append(['Причина отмены', 'Количество'])
            for k, v in st['by_reason'].items():
                ws.append([k, v])
            for cell in ws[1]:
                cell.font = Font(bold=True)
            wb.save(path)
            messagebox.showinfo('Экспорт', f'Файл сохранён:\n{path}')

        def export_pdf():
            if not last[0]:
                messagebox.showinfo('Экспорт', 'Нет данных для экспорта. Сначала сформируйте сводный отчёт.')
                return
            try:
                from reportlab.lib.pagesizes import A4
                from reportlab.pdfbase import pdfmetrics
                from reportlab.pdfbase.ttfonts import TTFont
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib import colors
                from reportlab.lib.styles import getSampleStyleSheet
            except ImportError:
                messagebox.showerror('Экспорт', 'Для PDF установите пакет reportlab')
                return
            path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
                                                initialfile='otchet_assol.pdf')
            if not path:
                return
            font = 'Helvetica'
            candidates = [r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\segoeui.ttf']
            for fp in candidates:
                if os.path.exists(fp):
                    try:
                        pdfmetrics.registerFont(TTFont('AppFont', fp))
                        font = 'AppFont'
                        break
                    except Exception:
                        pass
            st = last[0]
            styles = getSampleStyleSheet()
            styles['Normal'].fontName = font
            styles['Title'].fontName = font
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
            story = [Paragraph('Сводный отчёт клиники «Ассоль»', styles['Title']),
                     Paragraph(f'Период: {sv.get()} — {ev.get()}', styles['Normal']), Spacer(1, 12)]
            story.append(Table(
                [['Показатель', 'Значение'], ['Общее количество записей', st['total']],
                 ['Активных/завершённых', st['active']], ['Отменённых', st['cancelled']],
                 ['Первичных обращений', st['primary']]], repeatRows=1,
                style=TableStyle([('GRID', (0, 0), (-1, -1), .5, colors.grey),
                                  ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)])))
            for title, data in [('Записи по врачам', st['by_doctor']), ('Записи по услугам', st['by_service']),
                                ('Отмены по причинам', st['by_reason'])]:
                story += [Spacer(1, 12), Paragraph(title, styles['Heading2']),
                          Table([['Наименование', 'Количество']] + [[k, v] for k, v in data.items()], repeatRows=1,
                                style=TableStyle([('GRID', (0, 0), (-1, -1), .5, colors.grey),
                                                  ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)]))]
            doc.build(story)
            messagebox.showinfo('Экспорт', f'Файл сохранён:\n{path}')

        ttk.Button(summary_bar, text='Сформировать сводный отчёт', style='Primary.TButton',
                   command=generate).pack(side='left', padx=4)
        ttk.Button(summary_bar, text='Экспорт в Excel', command=export_excel).pack(side='left', padx=4)
        ttk.Button(summary_bar, text='Экспорт в PDF', command=export_pdf).pack(side='left', padx=4)


if __name__ == '__main__':
    app = App()
    app.mainloop()