from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from documents import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Документы
    path('documents/', views.document_list, name='doc_list'),
    path('documents/personal/', views.personal_documents, name='personal_docs'),
    path('documents/doc/<int:pk>/', views.document_detail, name='doc_detail'),
    path('documents/download/<int:pk>/', views.download_document, name='download_document'),
    path('documents/sign/<int:pk>/', views.sign_document, name='sign_document'),
    path('documents/upload/', views.upload_document, name='upload_doc'),
    
    # Уведомления + профиль
    path('notifications/', views.notifications_view, name='notifications'),
    path('profile/', views.profile_view, name='profile'),
    
    # API поиска
    path('api/search-students/', views.search_students, name='search_students'),
    path('api/search-documents/', views.search_documents, name='search_documents'),
    path('api/search-recipients/', views.search_recipients, name='search_recipients'),
    
    # Отчёты
    path('reports/', views.report_document, name='report_document'),
    path('reports/doc/<int:doc_id>/', views.report_document, name='report_document_detail'),
    path('reports/pdf/<int:doc_id>/', views.generate_pdf_report, name='report_pdf'),
    
    # Кастомная админка
    path('control/', views.admin_dashboard, name='admin_dashboard'),
    path('control/users/', views.admin_users, name='admin_users'),
    path('control/users/create/', views.user_create, name='user_create'),
    path('control/users/edit/<int:pk>/', views.user_edit, name='user_edit'),
    path('control/users/delete/<int:pk>/', views.user_delete, name='user_delete'),
    path('control/categories/', views.admin_categories, name='admin_categories'),
    path('control/categories/create/', views.category_create, name='category_create'),
    path('control/categories/edit/<int:pk>/', views.category_edit, name='category_edit'),
    path('control/categories/delete/<int:pk>/', views.category_delete, name='category_delete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)