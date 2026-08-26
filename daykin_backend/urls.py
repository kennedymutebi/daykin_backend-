from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = 'Daykin Admin'
admin.site.site_title = 'Daykin'
admin.site.index_title = 'Daykin Dashboard'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/voice-wishes/', include('voice_wishes.urls')),   
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)