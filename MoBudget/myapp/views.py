from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from django.contrib import messages
from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from .forms import RegisterForm, ExpenseForm, CategoryForm, EarningForm, SourceForm, AccountBalanceForm, UserProfileForm
from .models import Expense, Category, Earning, Source, AccountBalance, AccountHistory
from django.db.models import Sum, Count
from django.views.generic import TemplateView
from datetime import timedelta
import csv
from django.http import JsonResponse
from django.http import HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.core.mail import send_mail
from django.conf import settings
from axes.utils import reset
from axes.models import AccessAttempt
from django.contrib.auth.models import User
import json
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear, TruncDate
from django.db.models.functions import ExtractMonth, ExtractYear
from collections import defaultdict
import datetime
import calendar

class WelcomeView(TemplateView):
    template_name = 'myapp/welcome.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('expenses:home')
        return super().dispatch(request, *args, **kwargs)

@login_required
def test(request):
    return render(request, 'myapp/test.html')

@login_required
def dashboard(request):
    # Get current time info
    now = timezone.now()

    # 1. All expenses for the user (to be used for the recent table)
    all_expenses = Expense.objects.filter(user=request.user).order_by('-date').select_related('category')
    all_earnings = Earning.objects.filter(user=request.user).order_by('-created_at')
    categories = Category.objects.filter(user=request.user)
    sources = Source.objects.filter(user=request.user)

    # 2. Calculate Total Spent for THIS MONTH ONLY
    # Filters by the current year and the current month
    monthly_spent = all_expenses.filter(
        date__year=now.year,
        date__month=now.month
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    monthly_earning = all_earnings.filter(
        date__year=now.year,
        date__month=now.month
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # 3. Count total categories
    category_count = Category.objects.filter(user=request.user).count()
    source_count = Source.objects.filter(user=request.user).count()

    # 4. Get recent expenses (first 5 for the table)
    recent_expenses = all_expenses[:5]
    recent_earnings = all_earnings[:5]

    total_earnings = monthly_earning*125

    accepted_earnings = Earning.objects.filter(user=request.user, status='accepted')

    # Calculate the sum of these earnings
    accepted_tot = accepted_earnings.aggregate(Sum('amount'))['amount__sum'] or 0
    accepted_total = accepted_tot*125
    # Count how many jobs are accepted
    accepted_count = accepted_earnings.count()

    # Define the statuses we want to group together
    pipeline_statuses = ['accepted', 'in_review', 'in_progress']

    # Filter earnings that fall into any of these categories
    pipeline_earnings = Earning.objects.filter(
        user=request.user,
        status__in=pipeline_statuses
    )

    # Calculate the total sum
    pipeline_tot = pipeline_earnings.aggregate(Sum('amount'))['amount__sum'] or 0
    pipeline_total = pipeline_tot*125
    earning_form = EarningForm(user=request.user)
    form = ExpenseForm(user=request.user)
    if request.method == 'POST':
        # CHECK FOR EXPENSE SUBMISSION
        if 'submit_expense' in request.POST:
            form = ExpenseForm(request.POST, user=request.user)
            expense = form.instance
            expense.user = request.user

            if form.is_valid():
                expense.save()

                # If it's an AJAX request (Add Another), return JSON instead of redirecting
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': f"Added {expense.description or 'Expense'}!"})

                messages.success(request, "Expense added!")
                return redirect('expenses:dashboard')
        # CHECK FOR INCOME SUBMISSION
        elif 'submit_income' in request.POST:
            earning_form = EarningForm(request.POST, user=request.user)
            if earning_form.is_valid():
                earning = earning_form.save(commit=False)
                earning.user = request.user
                earning.save()
                 # If it's an AJAX request (Add Another), return JSON instead of redirecting
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': f"Added {earning.description or 'Earning'}!"})

                messages.success(request, "Earning added!")
                return redirect('expenses:dashboard')

    context = {
        'recent_expenses': recent_expenses,
        'monthly_spent': monthly_spent, # Use this in your HTML
        'category_count': category_count,
        'categories': categories,
        'recent_earnings': recent_earnings,
        'monthly_earning': total_earnings,
        'source_count':source_count,
        'sources':sources,
        'accepted_total': accepted_total,
        'accepted_count': accepted_count,
        'pipeline_total': pipeline_total,
        'current_month_name': now.strftime('%B'), # e.g., "January"
        'form': form,
        'earning_form': earning_form,
    }

    return render(request, 'myapp/dashboard.html', context)

@login_required
def home(request):
    # Base queryset
    expenses = Expense.objects.filter(user=request.user).select_related('category')

    search_query = request.GET.get('q', '')

    # Apply Search Filter
    if search_query:
        expenses = expenses.filter(description__icontains=search_query)

    # --- 1. APPLY FILTERS ---
    category_id = request.GET.get('category')
    timeframe = request.GET.get('timeframe')

    exact_date = request.GET.get('exact_date') # New Parameter
    start_date = request.GET.get('start_date') # New
    end_date = request.GET.get('end_date')     # New

    # If the user just arrived (no query params), default to 'month'
    if timeframe is None and not any([category_id, request.GET.get('exact_date'), request.GET.get('start_date')]):
        timeframe = 'month'

    now = timezone.now().date()

    if category_id:
        expenses = expenses.filter(category_id=category_id)

    # Filtering Logic Hierarchy
    if exact_date:
        expenses = expenses.filter(date=exact_date)
    elif start_date and end_date:
        # Filter between two dates inclusive
        expenses = expenses.filter(date__range=[start_date, end_date])
    elif timeframe:
        if timeframe == 'today':
            expenses = expenses.filter(date=now)
        elif timeframe == 'week':
            expenses = expenses.filter(date__gte=now - timedelta(days=7))
        elif timeframe == 'month':
            expenses = expenses.filter(date__month=now.month, date__year=now.year)
        elif timeframe == 'year':
            expenses = expenses.filter(date__year=now.year)
        elif timeframe == 'this_week':
            # Calculate Monday of the current week
            # .weekday() returns: Mon=0, Tue=1 ... Sun=6
            start_of_week = now - timedelta(days=now.weekday())
            # Sunday is 6 days after Monday
            end_of_week = start_of_week + timedelta(days=6)

            expenses = expenses.filter(date__range=[start_of_week, end_of_week])

    if start_date and end_date:
        if start_date <= end_date:
            expenses = expenses.filter(date__range=[start_date, end_date])
        else:
            # If dates are invalid, we can ignore the range or show a message
            from django.contrib import messages
            messages.error(request, "Invalid date range selected.")

    # --- 2. DATA FOR PIE CHART ---
    # Grouping filtered expenses by category name
    chart_data = (
        expenses.values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('category__name')
    )

    # Prepare lists for Chart.js
    chart_labels = [item['category__name'] or 'Misc' for item in chart_data]
    chart_values = [float(item['total']) for item in chart_data]

    start_of_week = now - timedelta(days=now.weekday())
    # Sunday is 6 days after Monday
    end_of_week = start_of_week + timedelta(days=6)
    week_expenses = expenses.filter(date__range=[start_of_week, end_of_week])
    week_total = week_expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    categories = Category.objects.filter(user=request.user)

    expenses_qs = expenses.order_by('-date')

    # 1. Capture the total count of filtered items BEFORE pagination
    filtered_count = expenses_qs.count()

    # --- 3. PAGINATION LOGIC ---
    # Get the number of items to display (default to 10)
    per_page = request.GET.get('per_page', 10)
    # Get current page number
    page_number = request.GET.get('page')

    paginator = Paginator(expenses_qs, per_page)
    page_obj = paginator.get_page(page_number)

    #Add expense popup
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        expense = form.instance
        expense.user = request.user

        if form.is_valid():
            expense.save()

            # If it's an AJAX request (Add Another), return JSON instead of redirecting
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': f"Added {expense.description or 'Expense'}!"})

            messages.success(request, "Expense added!")
            return redirect('expenses:home')
    else:
        form = ExpenseForm(user=request.user)

    context = {
        'expenses': page_obj,  # We pass the page object instead of the queryset
        'search_query': search_query,
        'timeframe': timeframe,
        'count': filtered_count,
        'categories': categories,
        'total': total,
        'week_total':week_total,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'per_page': int(per_page), # Pass back to keep the dropdown selection
        'form': form,
    }
    return render(request, 'myapp/index.html', context)

@login_required
def export_expenses_csv(request):
    # 1. Base queryset
    expenses = Expense.objects.filter(user=request.user).select_related('category')

    # 2. Capture all filter parameters
    search_query = request.GET.get('q')
    category_id = request.GET.get('category')
    timeframe = request.GET.get('timeframe')
    exact_date = request.GET.get('exact_date')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    now = timezone.now()

    # Apply Search Filter
    if search_query:
        expenses = expenses.filter(description__icontains=search_query)

    # 3. Apply Filters (Matching the home view logic exactly)
    if category_id:
        expenses = expenses.filter(category_id=category_id)

    if exact_date:
        expenses = expenses.filter(date=exact_date)
    elif start_date and end_date:
        expenses = expenses.filter(date__range=[start_date, end_date])
    elif timeframe:
        if timeframe == 'today':
            expenses = expenses.filter(date=now.date())
        elif timeframe == 'this_week':
            # Calculate Monday of the current week
            # .weekday() returns: Mon=0, Tue=1 ... Sun=6
            start_of_week = now - timedelta(days=now.weekday())
            # Sunday is 6 days after Monday
            end_of_week = start_of_week + timedelta(days=6)
            expenses = expenses.filter(date__range=[start_of_week, end_of_week])
        elif timeframe == 'month':
            expenses = expenses.filter(date__month=now.month, date__year=now.year)
        elif timeframe == 'year':
            expenses = expenses.filter(date__year=now.year)

    filtered_total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    # 4. Generate CSV Response
    response = HttpResponse(content_type='text/csv')
    # Dynamic filename based on filters
    export_label = timeframe or exact_date or f"{start_date}_to_{end_date}" or "all"
    response['Content-Disposition'] = f'attachment; filename="expenses_{export_label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Description', 'Category', 'Amount'])
    for expense in expenses.order_by('-date'):
        writer.writerow([
            expense.date,
            expense.description,
            expense.category.name if expense.category else 'Misc',
            expense.amount
        ])
    writer.writerow(['', '', 'TOTAL:', f"Ksh {filtered_total}"])
    return response

def login_view(request):

    if 'next' in request.GET and not request.user.is_authenticated:
        messages.info(request, "Your session has expired. Please log in again to continue.")
    form = AuthenticationForm()
    limit = 4

    # 1. Initialize tracking data
    user_attempts = request.session.get('user_attempts', {})
    username = request.POST.get('username', '').strip()
    attempts_remaining = limit

    # 2. Sync with Admin Panel & Time (Pre-check)
    if username:
        # Check if Admin deleted the lockout record
        axes_record_exists = AccessAttempt.objects.filter(username=username).exists()

        # Check if the 1-hour cool-off has passed
        user_data = user_attempts.get(username, {})
        last_fail_str = user_data.get('last_fail')
        is_expired = False
        if last_fail_str:
            last_fail_time = timezone.datetime.fromisoformat(last_fail_str)
            if timezone.now() > last_fail_time + timedelta(hours=1):
                is_expired = True

        # If Admin cleared it OR time expired, reset the session counter
        if not axes_record_exists or is_expired:
            user_attempts[username] = {'count': 0, 'last_fail': None}
            request.session['user_attempts'] = user_attempts

        # Update display count
        current_fails = user_attempts.get(username, {}).get('count', 0)
        attempts_remaining = max(0, limit - current_fails)

    # 3. Handle Form Submission
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        user_exists = User.objects.filter(username=username).exists()

        if form.is_valid():

            # --- START REMEMBER ME LOGIC ---
            remember_me = request.POST.get('remember_me') # Matches 'name' in HTML
            if remember_me:
                # Set session to last for 2 weeks (in seconds)
                request.session.set_expiry(1209600)
            else:
                # Session expires when browser is closed
                request.session.set_expiry(0)
            # --- END REMEMBER ME LOGIC ---

            # SUCCESS: Wipe the slate clean for this user
            user_attempts[username] = {'count': 0, 'last_fail': None}
            request.session['user_attempts'] = user_attempts

            user = form.get_user()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('expenses:dashboard')

        else:
            # FAILURE: Only penalize if the account actually exists
            if username and user_exists:
                count = user_attempts.get(username, {}).get('count', 0) + 1
                user_attempts[username] = {
                    'count': count,
                    'last_fail': timezone.now().isoformat()
                }
                request.session['user_attempts'] = user_attempts
                attempts_remaining = max(0, limit - count)

    return render(request, 'myapp/login.html', {
        'form': form,
        'attempts_remaining': attempts_remaining
    })

def contact_admin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        message_content = request.POST.get('message')

        # 1. Construct the email
        subject = f"Lockout Support Request from {email}"
        full_message = f"User Email: {email}\n\nMessage:\n{message_content}"
        recipient_list = [settings.EMAIL_BACKEND] # Define this in settings.py

        # 2. Send the email
        send_mail(
            subject,
            full_message,
            email, # From email (the user)
            recipient_list,
            fail_silently=False,
        )

        messages.success(request, "Your request has been sent to the administrator. Please check your email for updates.")
        return redirect('expenses:login')

    return redirect('expenses:login')

def signup_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()
            messages.success(request, "Registration successful.")
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')  # Log in the user automatically
            return redirect('expenses:home')
        else:
            pass
    else:
        form = RegisterForm()
    return render(request, 'myapp/signup.html', {'form': form})

@login_required
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST, user=request.user)
        expense = form.instance
        expense.user = request.user

        if form.is_valid():
            expense.save()

            # If it's an AJAX request (Add Another), return JSON instead of redirecting
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': f"Added {expense.description or 'Expense'}!"})

            messages.success(request, "Expense added!")
            return redirect('expenses:home')
    else:
        form = ExpenseForm(user=request.user)

    return render(request, 'myapp/add_expense.html', {'form': form})

@login_required
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully!')

            # NEW: Check if a redirect destination was explicitly sent from the popup form
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)

            return redirect('expenses:dashboard')
    else:
        form = ExpenseForm(instance=expense, user=request.user)

    return render(request, 'myapp/edit_expense.html', {'form': form, 'expense': expense})

@login_required
def delete_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':
        description = expense.description or "No description"
        amount = expense.amount
        expense.delete()
        messages.success(request, f"Expense of ${amount} ({description}) successfully deleted.")
        return redirect('expenses:home')

    # If GET, show confirmation page (optional — we'll use modal instead)
    return redirect('expenses:home')  # Or render a confirm template if preferred

@login_required
def delete_expense_dashboard(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)

    if request.method == 'POST':
        description = expense.description or "No description"
        amount = expense.amount
        expense.delete()
        messages.success(request, f"Expense of ${amount} ({description}) successfully deleted.")
        return redirect('expenses:dashboard')

    # If GET, show confirmation page (optional — we'll use modal instead)
    return redirect('expenses:dashboard')  # Or render a confirm template if preferred

@login_required
def add_category(request):
    if request.method == 'POST':
        # Pass user to the form for the clean_name validation
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f"Category '{category.name}' added!")
            return redirect('expenses:category_list')
    else:
        form = CategoryForm(user=request.user)

    return render(request, 'myapp/add_category.html', {'form': form})

@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).annotate(
        expense_count=Count('expenses')
    ).order_by('name')

    return render(request, 'myapp/category_list.html', {'categories': categories})

@login_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)

    if request.method == 'POST':
        # Pass both instance and user
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated!")
            return redirect('expenses:category_list')
    else:
        form = CategoryForm(instance=category, user=request.user)

    return render(request, 'myapp/edit_category.html', {'form': form, 'category': category})

@login_required
def delete_category(request, pk):
    # 1. Secure lookup: Ensure the category exists AND belongs to the current user
    category = get_object_or_404(Category, pk=pk, user=request.user)

    # 2. Safety check: Check if any expenses (for this specific user) use this category
    if Expense.objects.filter(category=category, user=request.user).exists():
        messages.error(
            request,
            f"Cannot delete '{category.name}' — it is assigned to one or more expenses."
        )
    else:
        name = category.name
        category.delete()
        messages.success(request, f"Category {name} deleted successfully.")

    return redirect('expenses:category_list')

@login_required
def add_earning(request):
    if request.method == 'POST':
        form = EarningForm(request.POST, user=request.user)
        if form.is_valid():
            earning = form.save(commit=False)
            earning.user = request.user
            earning.save()
            messages.success(request, 'Earning added successfully!')
            return redirect('expenses:earning_list') # Redirect to your dashboard

    else:
        form = EarningForm(user=request.user)

    return render(request, 'myapp/add_earning.html', {'form': form})

@login_required
def earning_list(request):
    # Base queryset
    earnings = Earning.objects.filter(user=request.user).select_related('source').order_by('created_at')

    search_query = request.GET.get('q', '')

    # Apply Search Filter
    if search_query:
        earnings = earnings.filter(description__icontains=search_query)

    # --- 1. APPLY FILTERS ---
    source_id = request.GET.get('source')
    timeframe = request.GET.get('timeframe')

    exact_date = request.GET.get('exact_date') # New Parameter
    start_date = request.GET.get('start_date') # New
    end_date = request.GET.get('end_date')     # New

    # If the user just arrived (no query params), default to 'month'
    if timeframe is None and not any([source_id, request.GET.get('exact_date'), request.GET.get('start_date')]):
        timeframe = 'month'

    now = timezone.now()

    if source_id:
        earnings = earnings.filter(source_id=source_id)

    # Filtering Logic Hierarchy
    if exact_date:
        earnings = earnings.filter(date=exact_date)
    elif start_date and end_date:
        # Filter between two dates inclusive
        earnings = earnings.filter(date__range=[start_date, end_date])
    elif timeframe:
        if timeframe == 'today':
            earnings = earnings.filter(date=now.date())
        elif timeframe == 'week':
            earnings = earnings.filter(date__gte=now - timedelta(days=7))
        elif timeframe == 'month':
            earnings = earnings.filter(date__month=now.month, date__year=now.year)
        elif timeframe == 'year':
            earnings = earnings.filter(date__year=now.year)
        elif timeframe == 'this_week':
            # Calculate Monday of the current week
            # .weekday() returns: Mon=0, Tue=1 ... Sun=6
            start_of_week = now - timedelta(days=now.weekday())
            # Sunday is 6 days after Monday
            end_of_week = start_of_week + timedelta(days=6)

            earnings = earnings.filter(date__range=[start_of_week, end_of_week])

    if start_date and end_date:
        if start_date <= end_date:
            earnings = earnings.filter(date__range=[start_date, end_date])
        else:
            # If dates are invalid, we can ignore the range or show a message
            from django.contrib import messages
            messages.error(request, "Invalid date range selected.")

    # --- 2. DATA FOR PIE CHART ---
    # Grouping filtered expenses by category name
    chart_data = (
        earnings.values('source__name')
        .annotate(total=Sum('amount'))
        .order_by('source__name')
    )

    # Prepare lists for Chart.js
    chart_labels = [item['source__name'] or 'Source' for item in chart_data]
    chart_values = [float(item['total']) for item in chart_data]

    start_of_week = now - timedelta(days=now.weekday())
    # Sunday is 6 days after Monday
    end_of_week = start_of_week + timedelta(days=6)
    this_week_earnings = earnings.filter(date__range=[start_of_week, end_of_week])

    total_earnings = earnings.aggregate(Sum('amount'))['amount__sum'] or 0
    total = total_earnings*125
    sources = Source.objects.filter(user=request.user)

    total_this_week_earnings = this_week_earnings.aggregate(Sum('amount'))['amount__sum'] or 0
    week_total = total_this_week_earnings*125

    earnings_qs = earnings.order_by('-created_at')

    # 1. Capture the total count of filtered items BEFORE pagination
    filtered_count = earnings_qs.count()

    #Add income popup
    if request.method == 'POST':
        earning_form = EarningForm(request.POST, user=request.user)
        if earning_form.is_valid():
            earning = earning_form.save(commit=False)
            earning.user = request.user
            earning.save()
            # If it's an AJAX request (Add Another), return JSON instead of redirecting
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': f"Added {earning.description or 'Earning'}!"})

            django_messages.success(request, "Earning added!")
            return redirect('expenses:earning_list')

    else:
        earning_form = EarningForm(user=request.user)

    # --- 3. PAGINATION LOGIC ---
    # Get the number of items to display (default to 10)
    per_page = request.GET.get('per_page', 10)
    # Get current page number
    page_number = request.GET.get('page')

    paginator = Paginator(earnings_qs, per_page)
    page_obj = paginator.get_page(page_number)



    context = {
        'earnings': page_obj,  # We pass the page object instead of the queryset
        'search_query': search_query,
        'timeframe': timeframe,
        'count': filtered_count,
        'sources': sources,
        'total': total,
        'week_total':week_total,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'per_page': int(per_page), # Pass back to keep the dropdown selection
        'earning_form':earning_form,
    }
    return render(request, 'myapp/earning_list.html', context)

@login_required
def delete_earning(request, pk):
    earning = get_object_or_404(Earning, pk=pk, user=request.user)

    if request.method == 'POST':
        description = earning.description or "No description"
        amount = earning.amount
        earning.delete()
        messages.success(request, f"Earning of ${amount} ({description}) successfully deleted.")
        return redirect('expenses:earning_list')

    # If GET, show confirmation page (optional — we'll use modal instead)
    return redirect('expenses:earning_list')  # Or render a confirm template if preferred

def export_earnings_csv(request):
    # 1. Base queryset
    earnings = Earning.objects.filter(user=request.user).select_related('source')

    # 2. Capture all filter parameters
    search_query = request.GET.get('q')
    source_id = request.GET.get('source')
    timeframe = request.GET.get('timeframe')
    exact_date = request.GET.get('exact_date')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    now = timezone.now()

    # Apply Search Filter
    if search_query:
        earnings = earnings.filter(description__icontains=search_query)

    # 3. Apply Filters (Matching the home view logic exactly)
    if source_id:
        earnings = earnings.filter(source_id=source_id)

    if exact_date:
        earnings = earnings.filter(date=exact_date)
    elif start_date and end_date:
        earnings = earnings.filter(date__range=[start_date, end_date])
    elif timeframe:
        if timeframe == 'today':
            earnings = earnings.filter(date=now.date())
        elif timeframe == 'this_week':
            # Calculate Monday of the current week
            # .weekday() returns: Mon=0, Tue=1 ... Sun=6
            start_of_week = now - timedelta(days=now.weekday())
            # Sunday is 6 days after Monday
            end_of_week = start_of_week + timedelta(days=6)
            earnings = earnings.filter(date__range=[start_of_week, end_of_week])

        elif timeframe == 'month':
            earnings = earnings.filter(date__month=now.month, date__year=now.year)
        elif timeframe == 'year':
            earnings = earnings.filter(date__year=now.year)
    total_earnings = earnings.aggregate(Sum('amount'))['amount__sum'] or 0
    filtered_total = total_earnings*125
    fil_total = float(filtered_total)
    # 4. Generate CSV Response
    response = HttpResponse(content_type='text/csv')
    # Dynamic filename based on filters
    export_label = timeframe or exact_date or f"{start_date}_to_{end_date}" or "all"
    response['Content-Disposition'] = f'attachment; filename="earnings_{export_label}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Description', 'Source', 'Status', 'Amount'])

    for earning in earnings.order_by('created_at'):
        writer.writerow([
            earning.date,
            earning.description,
            earning.source.name if earning.source else 'Source',
            earning.status,
            earning.amount
        ])
    writer.writerow(['', '', '', 'TOTAL:', f"Ksh {fil_total}"])
    return response

@login_required
def edit_earning(request, pk):
    # Fetch the specific earning or 404 if not found/not yours
    earning = get_object_or_404(Earning, pk=pk, user=request.user)

    if request.method == 'POST':
        # Pass the instance to the form so it updates the existing record
        form = EarningForm(request.POST, instance=earning, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Earning updated successfully!')

            # NEW: Check if a redirect destination was explicitly sent from the popup form
            next_url = request.POST.get('next')
            if next_url:
                return redirect(next_url)

            return redirect('expenses:earning_list')
    else:
        # Pre-fill the form with existing data
        form = EarningForm(instance=earning, user=request.user)

    return render(request, 'myapp/edit_earning.html', {
        'form': form,
        'earning': earning
    })

@login_required
def delete_earning_dashboard(request, pk):
    earning = get_object_or_404(Earning, pk=pk, user=request.user)

    if request.method == 'POST':
        description = earning.description or "No description"
        amount = earning.amount
        earning.delete()
        messages.success(request, f"Earning of ${amount} ({description}) successfully deleted.")
        return redirect('expenses:dashboard')

    # If GET, show confirmation page (optional — we'll use modal instead)
    return redirect('expenses:dashboard')  # Or render a confirm template if preferred
@login_required
def add_source(request):
    if request.method == 'POST':
        form = SourceForm(request.POST)
        if form.is_valid():
            source = form.save(commit=False)
            source.user = request.user
            source.save()
            messages.success(request, 'Income source added!')
            return redirect('expenses:source_list')
    else:
        form = SourceForm()

    return render(request, 'myapp/add_source.html', {'form': form})

@login_required
def source_list(request):
    sources = Source.objects.filter(user=request.user).annotate(
        earning_count=Count('earning')
    ).order_by('name')

    return render(request, 'myapp/source_list.html', {'sources': sources})


@login_required
def delete_source(request, pk):
    source = get_object_or_404(Source, pk=pk, user=request.user)

    if request.method == 'POST':
        description = source.description or "No description"
        name = source.name
        source.delete()
        messages.success(request, f"Source of {name} ({description}) successfully deleted.")
        return redirect('expenses:source_list')

    # If GET, show confirmation page (optional — we'll use modal instead)
    return redirect('expenses:source_list')  # Or render a confirm template if preferred

@login_required
def edit_source(request, pk):
    source = get_object_or_404(Source, pk=pk, user=request.user)

    if request.method == 'POST':
        # Pass both instance and user
        form = SourceForm(request.POST, instance=source)
        if form.is_valid():
            form.save()
            messages.success(request, "Source updated!")
            return redirect('expenses:source_list')
    else:
        form = SourceForm(instance=source)

    return render(request, 'myapp/edit_source.html', {'form': form, 'source': source})

@require_POST
def update_earning_status(request, pk):
    print(f"DEBUG: Attempting to update earning {pk}") # Check your console!
    try:
        data = json.loads(request.body)
        earning = Earning.objects.get(pk=pk, user=request.user)
        earning.status = data.get('status')
        earning.save()
        print(f"DEBUG: Saved status as {earning.status}")
        return JsonResponse({'status': 'success'})
    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def expense_reports(request):
    # 1. Capture query parameter filters from the request URL
    filter_type = request.GET.get('filter', 'daily')
    year_filter = request.GET.get('year')
    month_filter = request.GET.get('month')

    # 2. Map the time truncation strategy based on selected granularity
    trunc_map = {
        'daily': TruncDay('date'),
        'weekly': TruncWeek('date'),
        'monthly': TruncMonth('date'),
        'yearly': TruncYear('date'),
    }
    trunc_func = trunc_map.get(filter_type, TruncDay('date'))

    # 3. Build Base Queryset tied strictly to the authenticated user
    expenses_qs = Expense.objects.filter(user=request.user)

    # 4. Conditionally apply Year & Month lookup variations
    if year_filter and year_filter.isdigit():
        expenses_qs = expenses_qs.filter(date__year=year_filter)
    if month_filter and month_filter.isdigit():
        expenses_qs = expenses_qs.filter(date__month=month_filter)

    # 5. Determine the dynamic pagination row count threshold
    per_page = request.GET.get('per_page', '10')
    if not per_page.isdigit():
        per_page = 10
    else:
        per_page = int(per_page)

    # 6. Group metrics by the time period using Django ORM aggregation functions
    report_data = (
        expenses_qs.annotate(period=trunc_func)
        .values('period')
        .annotate(total_amount=Sum('amount'))
        .order_by('-period')
    )

    # 7. Coerce the lazy QuerySet into a standard Python list of dictionaries
    # This allows us to modify individual entry keys directly without database restrictions
    report_data = list(report_data)

    # 8. Compute the grand total across all records found using list comprehension
    total_amount = sum(item['total_amount'] or 0 for item in report_data)

    # 9. Loop over the parsed records to format empty defaults and extend weekly date ranges
    for item in report_data:
        item['total_amount'] = (item['total_amount'] or 0)

        # Calculate trailing weekend offset (+6 days) if weekly mode is engaged
        if filter_type == 'weekly' and item['period']:
            item['end_period'] = item['period'] + timedelta(days=6)

    # 10. Extract a clean, distinct list of historical calendar years for select filters
    years = (
        Expense.objects.filter(user=request.user)
        .annotate(y=ExtractYear('date'))
        .values_list('y', flat=True)
        .distinct()
        .order_by('-y')
    )

    years = [str(y) for y in years]

    # 11. Run the slice operations through the Django Paginator engine
    paginator = Paginator(report_data, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 12. Deliver context blocks smoothly into your presentation layer
    context = {
        'report_data': page_obj,  # Pass the paginated object containing list fragments
        'filter_type': filter_type,
        'year_filter': year_filter,
        'month_filter': month_filter,
        'total_sum': total_amount,
        'years': years,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'per_page': per_page,
    }
    return render(request, 'myapp/expense_reports.html', context)

@login_required
def report_expenses_csv(request):
    filter_type = request.GET.get('filter', 'daily')
    year_filter = request.GET.get('year')
    month_filter = request.GET.get('month')

    expenses_qs = Expense.objects.filter(user=request.user)
    if year_filter and year_filter.isdigit():
        expenses_qs = expenses_qs.filter(date__year=year_filter)
    if month_filter and month_filter.isdigit():
        expenses_qs = expenses_qs.filter(date__month=month_filter)

    trunc_map = {'daily': TruncDay('date'), 'weekly': TruncWeek('date'),
                 'monthly': TruncMonth('date'), 'yearly': TruncYear('date')}
    trunc_func = trunc_map.get(filter_type, TruncDay('date'))

    report_data = expenses_qs.annotate(period=trunc_func).values('period').annotate(total_amount=Sum('amount')).order_by('-period')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="expenses_{filter_type}_{year_filter or "all"}.csv"'

    period = ""
    if filter_type == 'daily':
        period = "Date"
    if filter_type == 'weekly':
        period = "Week"
    if filter_type == 'monthly':
        period = "Month"
    if filter_type == 'yearly':
        period = "Year"

    writer = csv.writer(response)
    writer.writerow([period, 'Total Spent (Ksh)'])

    for item in report_data:
        amount_ksh = float(item['total_amount'] or 0)

        # Clean Date Formatting
        if filter_type == 'daily':
            date_label = item['period'].strftime('%Y-%m-%d')
        elif filter_type == 'monthly':
            date_label = item['period'].strftime('%B %Y')
        else:
            # Calculate the explicit +6 days end of the week interval
            start_date = item['period']
            end_date = start_date + timedelta(days=6)
            date_label = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"

        writer.writerow([date_label, f"{amount_ksh:,.2f}"])

    return response

@login_required
def earning_reports(request):
    filter_type = request.GET.get('filter', 'daily')
    status_filter = request.GET.get('status', 'all')
    year_filter = request.GET.get('year')
    month_filter = request.GET.get('month')

    # Get items per page from request dropdown params
    per_page = request.GET.get('per_page', '10')
    if not per_page.isdigit():
        per_page = 10
    else:
        per_page = int(per_page)

    trunc_map = {
        'daily': TruncDay('date'),
        'weekly': TruncWeek('date'),
        'monthly': TruncMonth('date'),
        'yearly': TruncYear('date'),
    }
    trunc_func = trunc_map.get(filter_type, TruncDay('date'))

    # Base Queryset
    earnings_qs = Earning.objects.filter(user=request.user)

    # 1. Apply Status Filter
    if status_filter != 'all':
        earnings_qs = earnings_qs.filter(status=status_filter)

    # 2. Apply Year Filter
    if year_filter and year_filter.isdigit():
        earnings_qs = earnings_qs.filter(date__year=year_filter)

    # 3. Apply Month Filter
    if month_filter and month_filter.isdigit():
        earnings_qs = earnings_qs.filter(date__month=month_filter)

    # Grouping logic
    report_data = (
        earnings_qs.annotate(period=trunc_func)
        .values('period')
        .annotate(total_amount=Sum('amount'))
        .order_by('-period')
    )

    # Coerce the database mapping query into an editable Python list of dicts
    report_data = list(report_data)

    # Calculate Totals dynamically across items in the list array
    # Base calculation multiplied by your conversion rate exchange factor (125)
    total_sum_ksh = sum((item['total_amount'] or 0) * 125 for item in report_data)

    # Loop through the list to attach custom properties
    for item in report_data:
        item['total_amount'] = item['total_amount'] or 0
        item['total_amount_ksh'] = item['total_amount'] * 125

        # NEW: Calculate the trailing weekend limit (+6 days) for weekly display blocks
        if filter_type == 'weekly' and item['period']:
            item['end_period'] = item['period'] + timedelta(days=6)

    # Prepare list of distinct historical years for dropdown menus
    years = (
        Earning.objects.filter(user=request.user)
        .annotate(y=ExtractYear('date'))
        .values_list('y', flat=True)
        .distinct()
        .order_by('-y')
    )
    # Convert the queryset values to a list of strings so templates never localize them
    years = [str(y) for y in years]

    # Pagination processing segment
    paginator = Paginator(report_data, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'report_data': page_obj, # Pass paginated data block slice context
        'filter_type': filter_type,
        'status_filter': status_filter,
        'year_filter': year_filter,
        'month_filter': month_filter,
        'total_sum': total_sum_ksh,
        'status_choices': Earning.STATUS_CHOICES,
        'years': years,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'per_page': per_page,
    }
    return render(request, 'myapp/earning_reports.html', context)

@login_required
def report_earnings_csv(request):
    # 1. Get all parameters
    filter_type = request.GET.get('filter', 'daily')
    status_filter = request.GET.get('status', 'all')
    year_filter = request.GET.get('year')
    month_filter = request.GET.get('month')

    # 2. Base Queryset
    earnings_qs = Earning.objects.filter(user=request.user)

    # 3. Apply all filters (Status, Year, Month)
    if status_filter != 'all':
        earnings_qs = earnings_qs.filter(status=status_filter)
    if year_filter and year_filter.isdigit():
        earnings_qs = earnings_qs.filter(date__year=year_filter)
    if month_filter and month_filter.isdigit():
        earnings_qs = earnings_qs.filter(date__month=month_filter)

    # 4. Truncation Logic
    trunc_map = {
        'daily': TruncDay('date'),
        'weekly': TruncWeek('date'),
        'monthly': TruncMonth('date'),
        'yearly': TruncYear('date')
    }
    trunc_func = trunc_map.get(filter_type, TruncDay('date'))

    report_data = (
        earnings_qs.annotate(period=trunc_func)
        .values('period')
        .annotate(total_amount=Sum('amount'))
        .order_by('-period')
    )

    # 5. Prepare Response
    response = HttpResponse(content_type='text/csv')
    filename = f"earnings_{filter_type}_{year_filter or 'all'}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    period = ""
    if filter_type == 'daily':
        period = "Date"
    if filter_type == 'weekly':
        period = "Week"
    if filter_type == 'monthly':
        period = "Month"
    if filter_type == 'yearly':
        period = "Year"

    writer = csv.writer(response)
    writer.writerow([period, 'Total Earned (Ksh)'])

    for item in report_data:
        # Currency conversion with fallback to 0
        amount = float(item['total_amount'] or 0) * 125

        # Dynamic date formatting for the CSV rows
        if filter_type == 'daily':
            date_label = item['period'].strftime('%Y-%m-%d')
        elif filter_type == 'monthly':
            date_label = item['period'].strftime('%B %Y')
        elif filter_type == 'yearly':
            date_label = item['period'].strftime('%Y')
        else: # weekly
            # Calculate the explicit +6 days end of the week interval
            start_date = item['period']
            end_date = start_date + timedelta(days=6)
            date_label = f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')}"

        writer.writerow([date_label, f"{amount:,.2f}"])

    return response

@login_required
def account_dashboard(request):
    accounts = AccountBalance.objects.filter(user=request.user)
    total_balance = accounts.aggregate(Sum('balance'))['balance__sum'] or 0

    # 1. Grab activity logs
    activity_log = AccountHistory.objects.filter(
        account__user=request.user
    ).select_related('account').order_by('-updated_at')[:15]

    # 2. Dynamically calculate variance differences on the fly
    for history in activity_log:
        # Find the snapshot taken immediately BEFORE this current one for this specific account
        previous_snapshot = AccountHistory.objects.filter(
            account=history.account,
            updated_at__lt=history.updated_at
        ).order_by('-updated_at').first()

        if previous_snapshot:
            # Shift value = Current snapshot amount minus older baseline snapshot amount
            history.difference = history.balance_snapshot - previous_snapshot.balance_snapshot
        else:
            # If no previous record exists, the entire current balance is the initial addition shift
            history.difference = history.balance_snapshot

    form = AccountBalanceForm()

    context = {
        'accounts': accounts,
        'total_balance': total_balance,
        'activity_log': activity_log,
        'form': form,
    }
    return render(request, 'myapp/account_dashboard.html', context)


@login_required
def add_account_balance(request):
    if request.method == 'POST':
        form = AccountBalanceForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()

            account_name = account.account_name
            messages.success(request, f"'{account_name}' was successfully added.")

            # UPDATED: Redirect smoothly right back to the account dashboard panel layout
            return redirect('expenses:account_dashboard_main')

    return redirect('expenses:account_dashboard_main')

@login_required
def edit_account_balance(request, pk):
    # Lock down the check query rules to matching primary key and authenticated requesting user
    account = get_object_or_404(AccountBalance, pk=pk, user=request.user)

    if request.method == 'POST':
        account.account_name = request.POST.get('account_name')
        account.account_type = request.POST.get('account_type')
        account.balance = request.POST.get('balance')
        account.notes = request.POST.get('notes')
        account.save() # This save command fires off your AccountHistory tracking signal instantly!

        account_name = account.account_name
        messages.success(request, f"'{account_name}' was successfully updated.")

    return redirect('expenses:account_dashboard_main')

@login_required
def delete_account_balance(request, pk):
    account = get_object_or_404(AccountBalance, pk=pk, user=request.user)

    if request.method == 'POST':
        account_name = account.account_name # Save string reference before removal
        account.delete()

        # Dispatch alert notification payload to session flash memory
        messages.success(request, f"'{account_name}' was successfully removed from your portfolio.")

    return redirect('expenses:account_dashboard_main')

@login_required
def daily_balance_ledger(request):
    user_accounts = AccountBalance.objects.filter(user=request.user).order_by('account_name')

    history_records = AccountHistory.objects.filter(
        account__user=request.user
    ).select_related('account').annotate(
        date=TruncDate('updated_at')
    ).order_by('date', 'updated_at')

    daily_matrix = defaultdict(dict)
    for record in history_records:
        daily_matrix[record.date][record.account.id] = record.balance_snapshot

    running_balances = {}
    ledger_data = []
    sorted_dates = sorted(daily_matrix.keys())
    previous_day_total = None

    for date in sorted_dates:
        day_total = 0
        account_values = {}

        for acc in user_accounts:
            if acc.id in daily_matrix[date]:
                running_balances[acc.id] = daily_matrix[date][acc.id]

            current_val = running_balances.get(acc.id, 0)
            account_values[acc.id] = current_val
            day_total += current_val

        if previous_day_total is not None:
            difference = day_total - previous_day_total
        else:
            difference = 0

        ledger_data.append({
            'date': date,
            'account_values': account_values,
            'day_total': day_total,
            'difference': difference,
        })

        previous_day_total = day_total

    ledger_data.reverse()

    # ==========================================
    # NEW: PAGINATION LOGIC
    # ==========================================
    # Show 10 ledger entries per page
    paginator = Paginator(ledger_data, 10)

    # Grab the current page number from the URL request parameters (e.g., /ledger/?page=2)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        # If page parameters are not an integer, default load the first page view
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page parameter is out of range, serve up the final page results
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'user_accounts': user_accounts,
        'ledger_data': page_obj, # Pass the paginated page object instead of the whole raw list
    }
    return render(request, 'myapp/daily_ledger.html', context)

@login_required
def export_ledger_csv(request):
    # 1. Gather all unique user account records in order
    user_accounts = AccountBalance.objects.filter(user=request.user).order_by('account_name')

    # 2. Extract historical structural timelines
    history_records = AccountHistory.objects.filter(
        account__user=request.user
    ).select_related('account').annotate(
        date=TruncDate('updated_at')
    ).order_by('date', 'updated_at')

    # 3. Process records into a temporary daily matrix dictionary
    daily_matrix = defaultdict(dict)
    for record in history_records:
        daily_matrix[record.date][record.account.id] = record.balance_snapshot

    # 4. Initialize stream data structures
    running_balances = {}
    sorted_dates = sorted(daily_matrix.keys())
    previous_day_total = None

    # Set up HTTP Response header directives to instruct browser to handle as an attachment download
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="daily_ledger_{request.user.username}.csv"'

    writer = csv.writer(response)

    # 5. Write the Header Row
    headers = ['Date'] + [acc.account_name for acc in user_accounts] + ['Total Balance', 'Daily Shift']
    writer.writerow(headers)

    # 6. Accumulate daily rows chronological order for calculation accuracy
    rows_data = []
    for date in sorted_dates:
        day_total = 0
        row = [date.strftime('%Y-%m-%d')]

        for acc in user_accounts:
            if acc.id in daily_matrix[date]:
                running_balances[acc.id] = daily_matrix[date][acc.id]
            current_val = running_balances.get(acc.id, 0.00)
            row.append(f"{current_val:.2f}")
            day_total += current_val

        row.append(f"{day_total:.2f}")

        if previous_day_total is not None:
            shift = day_total - previous_day_total
            row.append(f"{shift:.2f}")
        else:
            row.append("0.00")

        rows_data.append(row)
        previous_day_total = day_total

    # Reverse data list rows so newest dates are stacked on top before printing to output stream
    rows_data.reverse()
    for r in rows_data:
        writer.writerow(r)

    return response

@login_required
def user_settings(request):
    # Initialize both forms for rendering fallback configurations
    profile_form = UserProfileForm(instance=request.user)
    password_form = PasswordChangeForm(user=request.user)

    # Track the active display tab using query parameter or tracking flag
    active_tab = 'profile'

    if request.method == 'POST':
        # PROCESS PROFILE UPDATE ACTION
        if 'update_profile' in request.POST:
            profile_form = UserProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile details were updated successfully!')
                return redirect('expenses:settings') # Adjust namespace mapping if needed
            active_tab = 'profile'

        # PROCESS PASSWORD CHANGE ACTION
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                # IMPORTANT: Keeps the user logged in after their password changes
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('expenses:settings')
            else:
                messages.error(request, 'Please correct the validation errors below.')
            active_tab = 'security'

    context = {
        'profile_form': profile_form,
        'password_form': password_form,
        'active_tab': active_tab,
    }
    return render(request, 'myapp/settings.html', context)

def password_reset(request):
    return render(request, "myapp/password_reset.html")

def logout_view(request):
    logout(request)
    return redirect('expenses:welcome')