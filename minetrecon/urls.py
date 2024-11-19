from django.urls import path

from .views import login_view, upload_file, history_view, logout_view, view_documents

urlpatterns = [
    path('',login_view, name='login'),  # URL for the login page
    path('upload/', upload_file, name='upload_file'),
    path('history/', history_view, name='history'),
    path('logout/', logout_view, name='logout'),
    path('view_documents/', view_documents, name='view_documents'), 
]



