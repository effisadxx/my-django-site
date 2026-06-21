from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string
from .models import Document, DocumentCategory, Notification, UserProfile
from .forms import DocumentUploadForm, SignatureForm, SimpleUserCreateForm
import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ==================== АВТОРИЗАЦИЯ ====================

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.first_name or user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    return render(request, 'login.html')


def user_logout(request):
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('home')


# ==================== ГЛАВНАЯ СТРАНИЦА ====================

def home(request):
    public_docs = Document.objects.filter(is_public=True, is_published=True)[:6]
    total_documents = Document.objects.filter(is_public=True, is_published=True).count()
    
    personal_docs = []
    unread_count = 0
    if request.user.is_authenticated:
        personal_docs = Document.objects.filter(
            is_personal=True,
            recipients=request.user,
            is_published=True
        )[:6]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    return render(request, 'home.html', {
        'public_docs': public_docs,
        'personal_docs': personal_docs,
        'total_documents': total_documents,
        'unread_count': unread_count,
    })


# ==================== ДОКУМЕНТЫ ====================

def document_list(request):
    docs = Document.objects.filter(is_public=True, is_published=True).order_by('-created_at')
    
    search_query = request.GET.get('search')
    category_slug = request.GET.get('category')
    
    if search_query:
        docs = docs.filter(Q(title__icontains=search_query) | Q(description__icontains=search_query))
    if category_slug:
        docs = docs.filter(category__slug=category_slug)
    
    paginator = Paginator(docs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'documents/list.html', {
        'documents': page_obj,
        'categories': DocumentCategory.objects.all(),
        'search_query': search_query,
        'category_slug': category_slug,
    })


@login_required
def personal_documents(request):
    docs = Document.objects.filter(
        is_personal=True,
        recipients=request.user,
        is_published=True
    ).order_by('-created_at')
    
    return render(request, 'documents/personal.html', {'documents': docs})


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(Document, pk=pk, is_published=True)
    
    if not doc.can_access(request.user):
        messages.error(request, 'У вас нет доступа к этому документу')
        return redirect('home')
    
    Notification.objects.filter(user=request.user, document=doc).update(is_read=True)
    
    can_sign = doc.can_sign(request.user)
    
    return render(request, 'documents/detail.html', {
        'document': doc,
        'can_sign': can_sign,
        'signature_form': SignatureForm(),
    })


@login_required
def sign_document(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    
    if not doc.is_personal:
        messages.error(request, 'Общедоступные документы не требуют подписи')
        return redirect('doc_detail', pk=pk)
    
    if doc.has_signature:
        messages.warning(request, 'Документ уже подписан')
        return redirect('doc_detail', pk=pk)
    
    if not doc.can_sign(request.user):
        messages.error(request, 'У вас нет прав для подписи этого документа')
        return redirect('doc_detail', pk=pk)
    
    if request.method == 'POST':
        form = SignatureForm(request.POST)
        if form.is_valid():
            user = authenticate(username=request.user.username, password=form.cleaned_data['password'])
            if user:
                doc.has_signature = True
                doc.signed_by = request.user
                doc.signed_at = timezone.now()
                doc.signature_hash = f"SIG-{doc.pk}-{int(timezone.now().timestamp())}"
                
                if request.user in doc.recipients.all():
                    doc.student_signed = True
                    doc.student_signed_at = timezone.now()
                
                doc.save()
                messages.success(request, f'✅ Документ "{doc.title}" подписан')
                
                if doc.uploaded_by != request.user:
                    Notification.objects.create(
                        user=doc.uploaded_by,
                        title='📝 Документ подписан',
                        message=f'Документ "{doc.title}" подписан {request.user.get_full_name() or request.user.username}',
                        document=doc,
                        link=f'/documents/doc/{doc.pk}/'
                    )
            else:
                messages.error(request, '❌ Неверный пароль')
    
    return redirect('doc_detail', pk=pk)


@login_required
def download_document(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    
    if not doc.can_access(request.user):
        messages.error(request, 'У вас нет доступа к этому документу')
        return redirect('home')
    
    doc.downloads_count += 1
    doc.save()
    return redirect(doc.file.url)


@login_required
def upload_document(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and 
            request.user.profile.role in ['secretary', 'admin'])):
        messages.error(request, 'У вас нет прав для загрузки документов')
        return redirect('home')
    
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.save()
            
            # Получаем список ID выбранных получателей
            recipient_ids = request.POST.getlist('recipient_ids[]')
            recipient_type = request.POST.get('recipient_type', 'student')
            
            if recipient_ids:
                if recipient_type == 'student':
                    users = User.objects.filter(id__in=recipient_ids, profile__role='student')
                else:
                    users = User.objects.filter(id__in=recipient_ids, profile__role='teacher')
                
                doc.recipients.set(users)
                
                for user in users:
                    Notification.objects.create(
                        user=user,
                        title='📄 Новый личный документ',
                        message=f'Вам доступен документ: {doc.title}',
                        document=doc,
                        link=f'/documents/doc/{doc.pk}/'
                    )
                
                role_name = 'студентам' if recipient_type == 'student' else 'преподавателям'
                messages.success(request, f'✅ Документ "{doc.title}" отправлен {len(users)} {role_name}')
            
            messages.success(request, f'✅ Документ "{doc.title}" успешно загружен')
            return redirect('doc_detail', pk=doc.pk)
    else:
        form = DocumentUploadForm()
    
    return render(request, 'documents/upload.html', {'form': form})


# ==================== УВЕДОМЛЕНИЯ ====================

@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user)
    notifications.update(is_read=True)
    return render(request, 'notifications.html', {'notifications': notifications})


# ==================== ПРОФИЛЬ ====================

@login_required
def profile_view(request):
    return render(request, 'profile.html')


# ==================== API ПОИСКА ====================

def search_students(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)
    
    students = User.objects.filter(
        Q(profile__role='student'),
        Q(last_name__icontains=query) | Q(first_name__icontains=query) | Q(profile__group__icontains=query)
    ).select_related('profile')[:20]
    
    results = []
    for student in students:
        full_name = f"{student.last_name} {student.first_name}"
        if student.profile.patronymic:
            full_name += f" {student.profile.patronymic}"
        results.append({
            'id': student.id,
            'full_name': full_name,
            'group': student.profile.group
        })
    
    return JsonResponse(results, safe=False)


def search_documents(request):
    """API поиск документов по названию"""
    query = request.GET.get('q', '').strip()
    
    print(f"=== ПОИСК ДОКУМЕНТОВ ===")
    print(f"Запрос: '{query}'")
    print(f"Длина: {len(query)}")
    
    if len(query) < 1:
        return JsonResponse([], safe=False)
    
    # Ищем документы
    docs = Document.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query),
        is_published=True
    )
    
    print(f"Найдено документов: {docs.count()}")
    
    results = []
    for doc in docs[:20]:
        results.append({
            'id': doc.id,
            'title': doc.title,
            'created_at': doc.created_at.strftime('%d.%m.%Y')
        })
    
    print(f"Результатов: {len(results)}")
    return JsonResponse(results, safe=False)


def search_recipients(request):
    """API поиск получателей (студентов или преподавателей)"""
    query = request.GET.get('q', '').strip()
    recipient_type = request.GET.get('type', 'student')
    
    # Поиск с 1 символа
    if len(query) < 1:
        return JsonResponse([], safe=False)
    
    users = User.objects.filter(profile__role=recipient_type)
    
    results = []
    for user in users:
        full_name = f"{user.last_name} {user.first_name}".lower()
        if query.lower() in full_name:
            info = "Студент" if recipient_type == 'student' else "Преподаватель"
            if recipient_type == 'student' and user.profile.group:
                info += f", группа: {user.profile.group}"
            
            results.append({
                'id': user.id,
                'full_name': f"{user.last_name} {user.first_name}",
                'info': info
            })
        
        if len(results) >= 20:
            break
    
    return JsonResponse(results, safe=False)


# ==================== ОТЧЁТЫ ====================

@login_required
def report_document(request, doc_id=None):
    """Страница отчета по документу"""
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and 
            request.user.profile.role in ['secretary', 'admin'])):
        messages.error(request, 'Нет доступа к отчётам')
        return redirect('home')
    
    selected_doc = None
    if doc_id:
        selected_doc = get_object_or_404(Document, pk=doc_id, is_published=True)
    
    documents = Document.objects.filter(is_published=True).order_by('-created_at')
    report_data = []
    
    if selected_doc and selected_doc.is_personal:
        # Получаем получателей из ManyToMany
        recipients = selected_doc.recipients.all()
        
        print(f"=== ОТЧЁТ ===")
        print(f"Документ: {selected_doc.title}")
        print(f"Получателей: {recipients.count()}")
        
        for recipient in recipients:
            # Проверяем, подписал ли этот получатель
            student_signed = selected_doc.student_signed
            
            teacher_name = None
            teacher_role = None
            if selected_doc.has_signature and selected_doc.signed_by:
                if hasattr(selected_doc.signed_by, 'profile') and selected_doc.signed_by.profile.role != 'student':
                    teacher_name = selected_doc.signed_by.get_full_name() or selected_doc.signed_by.username
                    teacher_role = selected_doc.signed_by.profile.role
            
            report_data.append({
                'full_name': f"{recipient.last_name} {recipient.first_name}",
                'group': recipient.profile.group if hasattr(recipient, 'profile') else '',
                'student_signed': student_signed,
                'student_signed_at': selected_doc.student_signed_at if student_signed else None,
                'teacher_signed': teacher_name is not None,
                'teacher_name': teacher_name,
                'teacher_role': teacher_role,
                'teacher_signed_at': selected_doc.signed_at if teacher_name else None,
            })
    
    return render(request, 'reports/document_report.html', {
        'documents': documents,
        'selected_document': selected_doc,
        'report_data': report_data,
        'signed_count': sum(1 for r in report_data if r.get('student_signed', False)),
        'unsigned_count': sum(1 for r in report_data if not r.get('student_signed', False)),
        'total_students': len(report_data),
        'is_personal': selected_doc.is_personal if selected_doc else False,
    })


def generate_pdf_report(request, doc_id):
    """Генерация PDF-отчёта"""
    selected_doc = get_object_or_404(Document, pk=doc_id, is_published=True)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_{selected_doc.id}.pdf"'
    
    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    try:
        pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
        pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
    except:
        pass
    
    # Отступы
    left_margin = 25*mm
    right_margin = 25*mm
    top_margin = 20*mm
    y = height - top_margin
    
    # === ШАПКА ===
    # Эмблема (нормального размера)
    try:
        from reportlab.lib.utils import ImageReader
        import os
        img_path = os.path.join(os.path.dirname(__file__), '../static/img/emblema.png')
        if os.path.exists(img_path):
            img = ImageReader(img_path)
            c.drawImage(img, left_margin, y-12*mm, width=16*mm, height=16*mm, preserveAspectRatio=True, mask='auto')
    except:
        pass
    
    # Текст шапки (смещён вправо от эмблемы)
    text_x = left_margin + 20*mm
    c.setFont('Arial', 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(text_x, y+8*mm, "МИНИСТЕРСТВО ОБРАЗОВАНИЯ И НАУКИ РЕСПУБЛИКИ ТАТАРСТАН")
    c.setFillColorRGB(0, 0, 0)
    
    c.setFont('Arial-Bold', 13)
    c.drawString(text_x, y+1*mm, "ГАПОУ «АЛЬМЕТЬЕВСКИЙ ПОЛИТЕХНИЧЕСКИЙ ТЕХНИКУМ»")
    
    c.setFont('Arial', 7)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(text_x, y-6*mm, "г. Альметьевск, ул. Мира, д.10 | 8 (8553) 39-99-19 | info.almetpt@tatar.ru")
    c.setFillColorRGB(0, 0, 0)
    
    # Линия
    y -= 16*mm
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.line(left_margin, y, width - right_margin, y)
    y -= 10*mm
    
    # Заголовок
    c.setFont('Arial-Bold', 16)
    c.drawCentredString(width/2, y, "ОТЧЁТ ПО ДОКУМЕНТУ")
    y -= 8*mm
    
    c.setFont('Arial', 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(width/2, y, f"Сформирован: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
    c.setFillColorRGB(0, 0, 0)
    y -= 12*mm
    
    # === ИНФОРМАЦИЯ ===
    c.setFont('Arial-Bold', 11)
    c.drawString(left_margin, y, "Информация о документе")
    y -= 8*mm
    
    c.setFont('Arial', 10)
    c.drawString(left_margin, y, f"Название: {selected_doc.title}")
    y -= 6*mm
    c.drawString(left_margin, y, f"Описание: {selected_doc.description or 'Нет описания'}")
    y -= 6*mm
    c.drawString(left_margin, y, f"Дата создания: {selected_doc.created_at.strftime('%d.%m.%Y %H:%M')}")
    y -= 6*mm
    c.drawString(left_margin, y, f"Автор: {selected_doc.uploaded_by.get_full_name() or selected_doc.uploaded_by.username}")
    y -= 6*mm
    c.drawString(left_margin, y, f"Тип: {'Личный документ' if selected_doc.is_personal else 'Общедоступный документ'}")
    y -= 12*mm
    
    # === СТАТИСТИКА ===
    if selected_doc.is_personal:
        recipients = selected_doc.recipients.all()
        
        c.setFont('Arial-Bold', 11)
        c.drawString(left_margin, y, "Статистика подписания")
        y -= 8*mm
        
        signed_count = 0
        if selected_doc.student_signed:
            signed_count = recipients.count()
        
        total = recipients.count()
        unsigned = total - signed_count
        
        c.setFont('Arial', 10)
        c.drawString(left_margin, y, f"Всего получателей: {total}")
        y -= 6*mm
        c.drawString(left_margin, y, f"Подписали: {signed_count}")
        y -= 6*mm
        c.drawString(left_margin, y, f"Не подписали: {unsigned}")
        y -= 10*mm
        
        # === ТАБЛИЦА ===
        if recipients.exists():
            c.setFont('Arial-Bold', 11)
            c.drawString(left_margin, y, "Список подписаний")
            y -= 8*mm
            
            # Заголовки
            c.setFont('Arial-Bold', 9)
            c.drawString(left_margin, y, "№")
            c.drawString(left_margin + 15*mm, y, "ФИО получателя")
            c.drawString(left_margin + 80*mm, y, "Роль")
            c.drawString(left_margin + 115*mm, y, "Статус")
            c.drawString(left_margin + 155*mm, y, "Дата подписи")
            y -= 5*mm
            
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.setLineWidth(0.5)
            c.line(left_margin, y, width - right_margin, y)
            y -= 5*mm
            
            c.setFont('Arial', 9)
            for idx, recipient in enumerate(recipients, 1):
                # Проверяем, подписал ли этот получатель
                is_signed = selected_doc.student_signed
                
                c.drawString(left_margin, y, str(idx))
                c.drawString(left_margin + 15*mm, y, f"{recipient.last_name} {recipient.first_name}")
                c.drawString(left_margin + 80*mm, y, "Студент" if recipient.profile.role == 'student' else "Преподаватель")
                
                if is_signed:
                    c.setFillColorRGB(0, 0.5, 0)
                    c.drawString(left_margin + 115*mm, y, "Подписал")
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(left_margin + 155*mm, y, selected_doc.student_signed_at.strftime('%d.%m.%Y %H:%M') if selected_doc.student_signed_at else "—")
                else:
                    c.setFillColorRGB(0.7, 0, 0)
                    c.drawString(left_margin + 115*mm, y, "Не подписал")
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(left_margin + 155*mm, y, "—")
                
                y -= 7*mm
                if y < 30*mm:
                    c.showPage()
                    y = height - 20*mm
                    c.setFont('Arial', 9)
    
    else:
        c.setFont('Arial', 11)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(width/2, y, "Общедоступный документ не требует подписи")
        c.setFillColorRGB(0, 0, 0)
    
    # === ПОДВАЛ ===
    y -= 20*mm
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.5)
    c.line(left_margin, y, width - right_margin, y)
    y -= 7*mm
    c.setFont('Arial', 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(width/2, y, f"Отчёт сформирован: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    c.setFillColorRGB(0, 0, 0)
    
    c.save()
    return response


# ==================== КАСТОМНАЯ АДМИНКА ====================

@login_required
def admin_dashboard(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    return render(request, 'admin_panel/dashboard.html', {
        'total_users': User.objects.count(),
        'total_docs': Document.objects.count(),
        'total_categories': DocumentCategory.objects.count(),
    })


@login_required
def admin_users(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    users = User.objects.all().order_by('last_name', 'first_name')
    return render(request, 'admin_panel/users.html', {'users': users})


@login_required
def user_create(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    if request.method == 'POST':
        form = SimpleUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'✅ Пользователь {user.get_full_name()} успешно добавлен!')
            return redirect('admin_users')
        else:
            # Выводим ошибки формы
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SimpleUserCreateForm()
    
    return render(request, 'admin_panel/user_form.html', {'form': form})

@login_required
def user_edit(request, pk):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.profile.role = request.POST.get('role')
        user.profile.group = request.POST.get('group', '')
        user.profile.patronymic = request.POST.get('patronymic', '')
        user.profile.phone = request.POST.get('phone', '')
        
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        user.save()
        user.profile.save()
        messages.success(request, f'✅ Пользователь {user.get_full_name()} обновлён')
        return redirect('admin_users')
    
    return render(request, 'admin_panel/user_edit.html', {'user': user})


@login_required
def user_delete(request, pk):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    user = get_object_or_404(User, pk=pk)
    
    if user == request.user:
        messages.error(request, '❌ Нельзя удалить самого себя')
        return redirect('admin_users')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'✅ Пользователь {username} удалён')
        return redirect('admin_users')
    
    return render(request, 'admin_panel/user_confirm_delete.html', {'user': user})


@login_required
def admin_categories(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    categories = DocumentCategory.objects.all().order_by('order')
    return render(request, 'admin_panel/categories.html', {'categories': categories})


@login_required
def category_create(request):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = request.POST.get('slug')
        icon = request.POST.get('icon', 'bi-folder')
        order = request.POST.get('order', 0)
        
        if name and slug:
            DocumentCategory.objects.create(name=name, slug=slug, icon=icon, order=order)
            messages.success(request, f'✅ Категория "{name}" создана')
            return redirect('admin_categories')
        else:
            messages.error(request, 'Заполните название и slug')
    
    return render(request, 'admin_panel/category_form.html')


@login_required
def category_edit(request, pk):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    category = get_object_or_404(DocumentCategory, pk=pk)
    
    if request.method == 'POST':
        category.name = request.POST.get('name')
        category.slug = request.POST.get('slug')
        category.icon = request.POST.get('icon', 'bi-folder')
        category.order = request.POST.get('order', 0)
        category.save()
        messages.success(request, f'✅ Категория "{category.name}" обновлена')
        return redirect('admin_categories')
    
    return render(request, 'admin_panel/category_form.html', {'category': category})


@login_required
def category_delete(request, pk):
    if not (request.user.is_superuser or (hasattr(request.user, 'profile') and request.user.profile.role == 'admin')):
        messages.error(request, 'Нет доступа')
        return redirect('home')
    
    category = get_object_or_404(DocumentCategory, pk=pk)
    
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'✅ Категория "{name}" удалена')
        return redirect('admin_categories')
    
    return render(request, 'admin_panel/category_confirm_delete.html', {'category': category})