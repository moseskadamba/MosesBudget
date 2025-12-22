from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.conf import settings
from django.core.paginator import Paginator
from django.views.decorators.cache import cache_page
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import RegisterForm, LoginForm, ExpenseForm, CategoryForm
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import Expense, Category
from django.db.models import Count

@login_required
def home(request):
    # Get current user's expenses
    expenses = Expense.objects.filter(user=request.user).select_related('category').order_by('-date')
    
    # Optional: Get all categories (useful for filters or stats)
    categories = Category.objects.all()

    # Calculate total expenses
    total = sum(expense.amount for expense in expenses)

    context = {
        'expenses': expenses,
        'categories': categories,
        'total': total,
    }
    return render(request, 'myapp/index.html', context)

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('expenses:home')
    else:
        form = AuthenticationForm()
    return render(request, 'myapp/login.html', {'form': form})

def signup_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()
            messages.success(request, "Registration successful.")
            login(request, user)  # Log in the user automatically
            return redirect('expenses:home')
    else:
        form = RegisterForm()
    return render(request, 'myapp/signup.html', {'form': form})

@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user  # Assign logged-in user
            expense.save()
            messages.success(request, 'Expense added successfully!')
            return redirect('expenses:home')  # Redirect to homepage
    else:
        form = ExpenseForm()

    return render(request, 'myapp/add_expense.html', {'form': form})

@login_required
def edit_expense(request, pk):
    # Get expense, but ensure it belongs to the logged-in user
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully!')
            return redirect('expenses:home')
    else:
        form = ExpenseForm(instance=expense)
    
    return render(request, 'myapp/edit_expense.html', {'form': form, 'expense': expense})

@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    
    if request.method == 'POST':
        description = expense.description or "No description"
        amount = expense.amount
        expense.delete()
        messages.success(request, f"Expense of ${amount} ({description}) deleted.")
        return redirect('expenses:home')
    
    # If GET, show confirmation page (optional — we'll use modal instead)
    return redirect('expenses:home')  # Or render a confirm template if preferred

@login_required
def category_list(request):
    # Annotate each category with number of expenses
    categories = Category.objects.annotate(
        expense_count=Count('expenses')
    ).order_by('name')
    
    form = CategoryForm()

    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{form.cleaned_data['name']}' added!")
            return redirect('expenses:category_list')

    return render(request, 'myapp/category_list.html', {
        'categories': categories,
        'form': form,
    })

@login_required
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    
    # Check if any expenses use this category
    if Expense.objects.filter(category=category).exists():
        messages.error(
            request,
            f"Cannot delete '{category.name}' — it is assigned to one or more expenses."
        )
    else:
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted successfully.")
    
    return redirect('expenses:category_list')

@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    original_name = category.name  # Save for message

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{original_name}' updated to '{form.cleaned_data['name']}'!")
            return redirect('expenses:category_list')
    else:
        form = CategoryForm(instance=category)

    return render(request, 'myapp/edit_category.html', {
        'form': form,
        'category': category,
    })