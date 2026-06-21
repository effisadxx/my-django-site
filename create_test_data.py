import os
import django
from django.contrib.auth.models import User
from django.core.files.base import ContentFile

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from documents.models import Document, DocumentCategory, UserProfile, Notification

def create_test_data():
    print("🚀 Начинаем создание тестовых данных...")
    
    # 1. Создаем категории документов
    categories = [
        {'name': 'Приказы', 'slug': 'orders', 'icon': 'bi-file-text'},
        {'name': 'Расписание', 'slug': 'schedule', 'icon': 'bi-calendar-week'},
        {'name': 'Учебные материалы', 'slug': 'educational', 'icon': 'bi-journal-bookmark'},
        {'name': 'Справки', 'slug': 'certificates', 'icon': 'bi-patch-check'},
        {'name': 'Финансовые документы', 'slug': 'financial', 'icon': 'bi-calculator'},
        {'name': 'Методические указания', 'slug': 'methodical', 'icon': 'bi-book'},
    ]
    
    for cat_data in categories:
        cat, created = DocumentCategory.objects.get_or_create(
            slug=cat_data['slug'],
            defaults={'name': cat_data['name'], 'icon': cat_data['icon']}
        )
        if created:
            print(f"✅ Создана категория: {cat.name}")
    
    # 2. Создаем тестовых пользователей
    users_data = [
        {'username': 'admin', 'first_name': 'Админ', 'last_name': 'Администратор', 'email': 'admin@almetpt.ru', 'password': 'admin123', 'role': 'admin'},
        {'username': 'ivanov', 'first_name': 'Иван', 'last_name': 'Иванов', 'email': 'ivanov@almetpt.ru', 'password': 'student123', 'role': 'student', 'group': 'БУР-221б'},
        {'username': 'petrov', 'first_name': 'Петр', 'last_name': 'Петров', 'email': 'petrov@almetpt.ru', 'password': 'student123', 'role': 'student', 'group': 'АВ-251б'},
        {'username': 'sidorova', 'first_name': 'Мария', 'last_name': 'Сидорова', 'email': 'sidorova@almetpt.ru', 'password': 'student123', 'role': 'student', 'group': 'БУР-221б'},
        {'username': 'teacher1', 'first_name': 'Елена', 'last_name': 'Преподавательская', 'email': 'teacher@almetpt.ru', 'password': 'teacher123', 'role': 'teacher'},
        {'username': 'staff1', 'first_name': 'Сергей', 'last_name': 'Сотрудников', 'email': 'staff@almetpt.ru', 'password': 'staff123', 'role': 'staff'},
    ]
    
    created_users = []
    for user_data in users_data:
        user, created = User.objects.get_or_create(
            username=user_data['username'],
            defaults={
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'email': user_data['email'],
            }
        )
        if created:
            user.set_password(user_data['password'])
            user.save()
            
            # Создаем профиль
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': user_data['role'],
                    'group': user_data.get('group', ''),
                }
            )
            print(f"✅ Создан пользователь: {user.get_full_name()} ({user_data['role']})")
        created_users.append(user)
    
    # 3. Получаем категории
    orders_cat = DocumentCategory.objects.get(slug='orders')
    schedule_cat = DocumentCategory.objects.get(slug='schedule')
    educational_cat = DocumentCategory.objects.get(slug='educational')
    certificates_cat = DocumentCategory.objects.get(slug='certificates')
    
    # 4. Создаем тестовые PDF файлы
    def create_pdf_content(title):
        return ContentFile(f"""
        %PDF-1.4
        1 0 obj
        << /Type /Catalog /Pages 2 0 R >>
        endobj
        2 0 obj
        << /Type /Pages /Kids [3 0 R] /Count 1 >>
        endobj
        3 0 obj
        << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
        endobj
        trailer
        << /Root 1 0 R >>
        """.encode(), f"{title}.pdf")
    
    # 5. ОБЩЕДОСТУПНЫЕ ДОКУМЕНТЫ (видны всем)
    public_docs = [
        {
            'title': 'Приказ о начале учебного года',
            'category': orders_cat,
            'description': 'Приказ №245 от 01.09.2025 о начале учебного процесса',
            'is_public': True,
            'is_personal': False,
        },
        {
            'title': 'Расписание занятий на осенний семестр 2025-2026',
            'category': schedule_cat,
            'description': 'Расписание для всех специальностей',
            'is_public': True,
            'is_personal': False,
        },
        {
            'title': 'Методические указания по выполнению курсовых работ',
            'category': educational_cat,
            'description': 'Общие требования к оформлению курсовых проектов',
            'is_public': True,
            'is_personal': False,
        },
        {
            'title': 'Правила внутреннего распорядка',
            'category': orders_cat,
            'description': 'Правила поведения для студентов и сотрудников',
            'is_public': True,
            'is_personal': False,
        },
        {
            'title': 'График сдачи сессии',
            'category': schedule_cat,
            'description': 'Расписание экзаменов на зимнюю сессию',
            'is_public': True,
            'is_personal': False,
        },
        {
            'title': 'Положение о стипендиальном обеспечении',
            'category': certificates_cat,
            'description': 'Информация о стипендиях и выплатах',
            'is_public': True,
            'is_personal': False,
        },
    ]
    
    admin_user = User.objects.get(username='admin')
    
    for doc_data in public_docs:
        doc, created = Document.objects.get_or_create(
            title=doc_data['title'],
            defaults={
                'category': doc_data['category'],
                'description': doc_data['description'],
                'is_public': doc_data['is_public'],
                'is_personal': doc_data['is_personal'],
                'uploaded_by': admin_user,
                'file': create_pdf_content(doc_data['title']),
            }
        )
        if created:
            print(f"✅ Создан общий документ: {doc.title}")
    
    # 6. ЛИЧНЫЕ ДОКУМЕНТЫ ДЛЯ СТУДЕНТОВ
    student_ivanov = User.objects.get(username='ivanov')
    student_petrov = User.objects.get(username='petrov')
    student_sidorova = User.objects.get(username='sidorova')
    
    personal_docs = [
        {
            'title': 'Справка об обучении',
            'category': certificates_cat,
            'description': 'Справка для предоставления по месту требования',
            'user': student_ivanov,
            'is_public': False,
            'is_personal': True,
        },
        {
            'title': 'Зачётная книжка (осень 2025)',
            'category': educational_cat,
            'description': 'Результаты промежуточной аттестации',
            'user': student_ivanov,
            'is_public': False,
            'is_personal': True,
        },
        {
            'title': 'Справка о стипендии',
            'category': certificates_cat,
            'description': 'Справка о размере стипендии за сентябрь',
            'user': student_petrov,
            'is_public': False,
            'is_personal': True,
        },
        {
            'title': 'Индивидуальный учебный план',
            'category': educational_cat,
            'description': 'План обучения на 2025-2026 учебный год',
            'user': student_sidorova,
            'is_public': False,
            'is_personal': True,
        },
        {
            'title': 'Характеристика с места обучения',
            'category': certificates_cat,
            'description': 'Для предоставления в военкомат',
            'user': student_petrov,
            'is_public': False,
            'is_personal': True,
        },
    ]
    
    for doc_data in personal_docs:
        doc, created = Document.objects.get_or_create(
            title=doc_data['title'],
            personal_user=doc_data['user'],
            defaults={
                'category': doc_data['category'],
                'description': doc_data['description'],
                'is_public': doc_data['is_public'],
                'is_personal': doc_data['is_personal'],
                'uploaded_by': admin_user,
                'file': create_pdf_content(doc_data['title']),
            }
        )
        if created:
            print(f"✅ Создан личный документ: {doc.title} для {doc.personal_user.get_full_name()}")
            
            # Создаем уведомление для студента
            Notification.objects.create(
                user=doc.personal_user,
                title=f'📄 Новый документ: {doc.title}',
                message=f'Вам доступен новый документ: {doc.description}',
                document=doc,
                link=f'/documents/doc/{doc.pk}/'
            )
    
    # 7. Создаем уведомления для пользователей
    notifications_data = [
        {
            'user': student_ivanov,
            'title': 'Добро пожаловать в ЭДО!',
            'message': 'Вы успешно зарегистрированы в системе электронного документооборота',
        },
        {
            'user': student_petrov,
            'title': 'Обновление расписания',
            'message': 'В разделе "Общедоступные документы" опубликовано новое расписание',
        },
        {
            'user': User.objects.get(username='teacher1'),
            'title': 'Права на загрузку документов',
            'message': 'Как преподаватель, вы можете загружать документы и ставить электронную подпись',
        },
    ]
    
    for notif_data in notifications_data:
        Notification.objects.get_or_create(
            user=notif_data['user'],
            title=notif_data['title'],
            defaults={'message': notif_data['message']}
        )
    
    print("\n" + "="*50)
    print("🎉 ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ!")
    print("="*50)
    print("\n📋 ДЛЯ ВХОДА В СИСТЕМУ:")
    print("-" * 30)
    print("👨‍💼 АДМИНИСТРАТОР:")
    print("   Логин: admin")
    print("   Пароль: admin123")
    print("\n👨‍🎓 СТУДЕНТЫ:")
    print("   Логин: ivanov | Пароль: student123 (Иван Иванов, группа БУР-221б)")
    print("   Логин: petrov | Пароль: student123 (Петр Петров, группа АВ-251б)")
    print("   Логин: sidorova | Пароль: student123 (Мария Сидорова, группа БУР-221б)")
    print("\n👨‍🏫 ПРЕПОДАВАТЕЛЬ:")
    print("   Логин: teacher1 | Пароль: teacher123")
    print("\n👨‍💼 СОТРУДНИК:")
    print("   Логин: staff1 | Пароль: staff123")
    print("\n" + "="*50)
    print("📄 ТИПЫ ДОКУМЕНТОВ:")
    print("- Общедоступные - видны всем без авторизации")
    print("- Личные документы - видны только конкретному студенту")
    print("- Есть уведомления о новых документах")
    print("="*50)

if __name__ == '__main__':
    create_test_data()