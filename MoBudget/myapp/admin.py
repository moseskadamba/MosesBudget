# admin.py
from django.contrib import admin
from .models import Category, Expense, Earning, Source

admin.site.register(Category)
admin.site.register(Expense)
admin.site.register(Earning)
admin.site.register(Source)