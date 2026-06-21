from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('applicant', 'Абитуриент'),
        ('student', 'Студент'),
        ('teacher', 'Преподаватель'),
        ('secretary', 'Секретарь-делопроизводитель'),
        ('admin', 'Администратор'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='applicant')
    group = models.CharField(max_length=50, blank=True, verbose_name="Группа")
    patronymic = models.CharField(max_length=100, blank=True, verbose_name="Отчество")
    phone = models.CharField(max_length=20, blank=True)
    
    def get_full_name(self):
        parts = [self.user.last_name, self.user.first_name, self.patronymic]
        return ' '.join([p for p in parts if p])
    
    def __str__(self):
        return self.get_full_name()


class DocumentCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=50, default='bi-folder')
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.name


class Document(models.Model):
    RECIPIENT_TYPE_CHOICES = [
        ('student', 'Студент'),
        ('teacher', 'Преподаватель'),
    ]
    
    title = models.CharField(max_length=200)
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/')
    description = models.TextField(blank=True)
    
    is_public = models.BooleanField(default=True)
    is_personal = models.BooleanField(default=False)
    recipient_type = models.CharField(max_length=20, choices=RECIPIENT_TYPE_CHOICES, default='student')
    
    # Множество получателей (вместо одного personal_user)
    recipients = models.ManyToManyField(User, blank=True, related_name='received_docs')
    
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_docs')
    created_at = models.DateTimeField(default=timezone.now)
    downloads_count = models.IntegerField(default=0)
    is_published = models.BooleanField(default=True)
    
    # Электронная подпись
    has_signature = models.BooleanField(default=False)
    signed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='signed_docs')
    signed_at = models.DateTimeField(null=True, blank=True)
    signature_hash = models.CharField(max_length=255, blank=True)
    
    # Подпись студента
    student_signed = models.BooleanField(default=False)
    student_signed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        """Строковое представление документа"""
        # Если документ личный и есть получатели
        if self.is_personal:
            recipients = self.recipients.all()
            if recipients.exists():
                names = ", ".join([r.get_full_name() for r in recipients[:3]])
                if recipients.count() > 3:
                    names += f" и ещё {recipients.count() - 3}"
                return f"{self.title} (для: {names})"
            return f"{self.title} (личный, без получателей)"
        return self.title
    
    def can_access(self, user):
        """Проверка доступа к документу"""
        if not user.is_authenticated:
            return self.is_public
        if user.is_superuser:
            return True
        if self.is_public:
            return True
        if self.is_personal and user in self.recipients.all():
            return True
        if hasattr(user, 'profile') and user.profile.role in ['secretary', 'teacher', 'admin']:
            return True
        return False
    
    def can_sign(self, user):
        """Проверка права на подпись"""
        if user.is_superuser:
            return True
        if hasattr(user, 'profile'):
            if user.profile.role in ['secretary', 'teacher', 'admin']:
                return True
            if user.profile.role == 'student' and self.is_personal and user in self.recipients.all():
                return True
        return False


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class DocumentDownload(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)