from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def api_root(request):
    return JsonResponse({
        'message': 'Welcome to DevTrack API',
        'available_endpoints': {
            'reporters': '/api/reporters/',
            'issues': '/api/issues/'
        }
    })


urlpatterns = [
    path('', api_root, name='root'),
    path('admin/', admin.site.urls),
    path('api/', include('issues.urls')),
]
