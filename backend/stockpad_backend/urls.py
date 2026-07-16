from django.contrib import admin
from django.urls import path, include
from django.http import Http404

from django.conf import settings
from django.conf.urls.static import static

def no_frontend(request):
    raise Http404("This is a pure REST API. Use /api/ or /admin/")

urlpatterns = [
    path('', no_frontend),          # Root → 404 (no frontend here)
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
