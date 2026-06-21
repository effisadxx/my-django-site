from django import forms
from django.contrib.auth.models import User
from .models import Document, UserProfile

class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'category', 'file', 'description', 'is_public', 'is_personal']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название документа'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Краткое описание'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_personal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убираем лишние поля, которые не нужны
        self.fields['is_public'].label = "Общедоступный"
        self.fields['is_personal'].label = "Личный документ"


class SimpleUserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Пароль')
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label='Подтверждение пароля')
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}), label='Роль')
    group = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Группа (для студентов)')
    patronymic = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}), label='Отчество')
    
    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'email']
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Иванов'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Иван'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ivanov@almetpt.ru'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        role = cleaned_data.get('role')
        group = cleaned_data.get('group')
        
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Пароли не совпадают')
        
        if role == 'student' and not group:
            raise forms.ValidationError('Для студента обязательно указать группу')
        
        # Генерируем логин из ФИО
        last_name = cleaned_data.get('last_name', '').strip()
        first_name = cleaned_data.get('first_name', '').strip()
        
        if last_name and first_name:
            # Транслитерация (упрощённая)
            translit_map = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
                'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
                'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
                'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
                'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
                'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
                'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
                'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
                'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
            }
            
            # Транслитерируем фамилию и имя
            last_name_translit = ''.join(translit_map.get(c, c) for c in last_name)
            first_name_translit = ''.join(translit_map.get(c, c) for c in first_name)
            
            # Формируем логин: фамилия_инициалы (строчные буквы)
            username = f"{last_name_translit.lower()}_{first_name_translit[0].lower()}"
            
            # Проверяем уникальность
            counter = 1
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            
            cleaned_data['username'] = username
        else:
            raise forms.ValidationError('Укажите фамилию и имя')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                group=self.cleaned_data.get('group', ''),
                patronymic=self.cleaned_data.get('patronymic', '')
            )
        return user


class SignatureForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Подтвердите пароль")