# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Expense, Category, Earning, Source

class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "password1", "password2"]

class LoginForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ["username", "password"]

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['amount', 'category', 'description', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # 1. Pop the user out of the kwargs so it doesn't break the super() call
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # 2. Filter the category queryset based on the logged-in user
        if user:
            # 1. Filter the list
            categories = Category.objects.filter(user=user)
            self.fields['category'].queryset = categories

            # 2. Force the display text to ONLY show the name
            self.fields['category'].label_from_instance = lambda obj: obj.name

        self.fields['category'].empty_label = "Select a category (optional)"

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Groceries, Transport'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional description'}),
        }

    def __init__(self, *args, **kwargs):
        # 1. Capture the user from the view
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()

        # 2. Filter by name AND the specific user
        qs = Category.objects.filter(name__iexact=name, user=self.user)

        # Exclude current instance if editing
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("You already have a category with this name.")

        return name.title()

class EarningForm(forms.ModelForm):
    class Meta:
        model = Earning
        # Add 'status' here
        fields = ['amount', 'source', 'description', 'date', 'status']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'source': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}), # Add styling for status
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['source'].queryset = Source.objects.filter(user=user)
            # Remove username from display text
            self.fields['source'].label_from_instance = lambda obj: obj.name

        self.fields['source'].empty_label = "Select a source"

class SourceForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Salary, Side Hustle'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional details...'}),
        }