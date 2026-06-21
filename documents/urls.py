from django.urls import path
from . import views

urlpatterns = [
    path('', views.document_list, name='doc_list'),
    path('doc/<int:pk>/', views.document_detail, name='doc_detail'),
    path('upload/', views.upload_document, name='upload_doc'),
]