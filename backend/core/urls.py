from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health),
    path('session/', views.session), path('login/', views.sign_in), path('logout/', views.sign_out),
    path('books/', views.books), path('shelves/', views.shelves), path('stats/', views.stats),
    path('students/', views.students), path('loans/', views.loans), path('checkout/', views.checkout),
    path('loans/<int:pk>/return/', views.return_book), path('loans/<int:pk>/remind/', views.remind),
    path('scan-verify/', views.verify), path('labels/<str:kind>/<int:pk>/', views.label),
]
