from django.urls import path
from . import views
from .views import WelcomeView
from django.contrib.auth import views as auth_views

app_name = 'expenses'

urlpatterns = [
    path('home',views.home, name='home'),
    path('', WelcomeView.as_view(), name='welcome'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('test',views.test, name='test'),
    path('dashboard',views.dashboard, name='dashboard'),

    path('export-csv/', views.export_expenses_csv, name='export_csv'),
    path('password-reset/', views.password_reset, name='password-reset'),
    path('contact-admin/', views.contact_admin, name='contact_admin'),

    #Expense routes
    path('add/', views.add_expense, name='add_expense'),
    path('edit/<int:pk>/', views.edit_expense, name='edit_expense'),
    path('delete/<int:pk>/', views.delete_expense, name='delete_expense'),
    path('delete_dashboard/<int:pk>/', views.delete_expense_dashboard, name='delete_expense_dashboard'),

    #Earning routes
    path('add_income/', views.add_earning, name='add_income'),
    path('earnings/', views.earning_list, name='earning_list'),
    path('earnings/export/', views.export_earnings_csv, name='export_earnings_csv'),
    path('edit_earning/<int:pk>/', views.edit_earning, name='edit_earning'),
    path('delete_earning/<int:pk>/', views.delete_earning, name='delete_earning'),
    path('delete_earning_dashboard/<int:pk>/', views.delete_earning_dashboard, name='delete_earning_dashboard'),
    path('update-status/<int:pk>/', views.update_earning_status, name='update_earning_status'),

    #Sources routes
    path('add_source/', views.add_source, name='add_source'),
    path('sources/', views.source_list, name='source_list'),
    path('sources/edit/<int:pk>/', views.edit_source, name='edit_source'),
    path('delete_source/<int:pk>/', views.delete_source, name='delete_source'),


    # Category routes
    path('categories/', views.category_list, name='category_list'),
    path('add_category/', views.add_category, name='add_category'),
    path('categories/edit/<int:pk>/', views.edit_category, name='edit_category'),
    path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),

    #Account balances
    path('accounts/', views.account_dashboard, name='account_dashboard_main'),
    path('accounts/add/', views.add_account_balance, name='account_balances'),
    path('accounts/edit/<int:pk>/', views.edit_account_balance, name='edit_account_balance'),
    path('accounts/delete/<int:pk>/', views.delete_account_balance, name='delete_account_balance'),
    path('accounts/ledger/', views.daily_balance_ledger, name='daily_ledger'),
    path('accounts/ledger/export/', views.export_ledger_csv, name='export_ledger_csv'),

    path('settings/', views.user_settings, name='settings'),

    path('reports/expenses/', views.expense_reports, name='expense_reports'),
    path('reports/earnings/', views.earning_reports, name='earning_reports'),
    path('reports/expenses/export/', views.report_expenses_csv, name='report_expenses_csv'),
    path('reports/earnings/export/', views.report_earnings_csv, name='report_earnings_csv'),
]
