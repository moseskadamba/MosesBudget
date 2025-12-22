from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('home',views.home, name='home'),
    path('', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),

    #Expense routes
    path('add/', views.add_expense, name='add'),
    path('edit/<int:pk>/', views.edit_expense, name='edit_expense'),
    path('delete/<int:pk>/', views.delete_expense, name='delete_expense'),
    
    # Category routes
    path('categories/', views.category_list, name='category_list'),
    path('categories/edit/<int:pk>/', views.edit_category, name='edit_category'), 
    path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),
]
