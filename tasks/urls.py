from django.urls import path
from . import views
from tasks.views import alta_maquinaria

# -- codigo para el alta de maquinaria --

urlpatterns = [
    path('alta_maquinaria/', views.alta_maquinaria, name='alta_maquinaria'),
]
# ---