from django.urls import path

from .views import login_view, upload_file

urlpatterns = [
    path('',login_view, name='login'),  # URL for the login page
   
    path('upload/', upload_file, name='upload_file'),
    
    
]




