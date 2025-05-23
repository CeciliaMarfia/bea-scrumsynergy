from django.urls import path
from . import views
from application.views import machinery_registration

# -- codigo para el alta de maquinaria --
urlpatterns = [
    path('machinery_registration/', views.machinery_registration, name='machinery_registration'),
]
# ---