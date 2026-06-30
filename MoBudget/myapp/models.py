from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class Category(models.Model):
    # Link category to a specific user
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    # Removed unique=True so different users can have categories with the same name
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
        # This ensures a single user can't have duplicate category names
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    description = models.TextField(blank=True, null=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def clean(self):
        """
        Custom validation to ensure a user cannot link an expense
        to a category belonging to a different user.
        """
        # Add a check to see if self.user exists first
        if hasattr(self, 'user') and self.user and self.category:
            if self.category.user != self.user:
                raise ValidationError({
                    'category': "The selected category must belong to you."
                })

    def save(self, *args, **kwargs):
        # Only run full_clean if the user is already attached
        if self.user:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.amount} on {self.date}"

class Source(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sources')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Sources"
        ordering = ['name']
        # This ensures a single user can't have duplicate source names
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Earning(models.Model):
    # Define the choices
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('in_review', 'In Review'),
        ('accepted', 'Accepted'),
        ('paid', 'Paid'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def clean(self):
        """
        Custom validation to ensure a user cannot link an income
        to a source belonging to a different user.
        """
        # Add a check to see if self.user exists first
        if hasattr(self, 'user') and self.user and self.source:
            if self.source.user != self.user:
                raise ValidationError({
                    'source': "The selected source must belong to you."
                })

    def save(self, *args, **kwargs):
        # Only run full_clean if the user is already attached
        if self.user:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source.name if self.source else 'Income'} - {self.amount} ({self.get_status_display()})"

class AccountBalance(models.Model):
    ACCOUNT_TYPES = [
        ('bank', 'Bank Account'),
        ('mobile_money', 'Mobile Money (e.g., M-Pesa)'),
        ('cash', 'Cash on Hand'),
        ('credit', 'Credit Card/Loan'),
        ('jobs', 'Job Account'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="balances")
    account_name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='bank')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-balance']
        unique_together = ['user', 'account_name']

    def __str__(self):
        return f"{self.account_name} ({self.user.username})"

# NEW: Model to track account historical snapshots
class AccountHistory(models.Model):
    account = models.ForeignKey(AccountBalance, on_delete=models.CASCADE, related_name="history")
    balance_snapshot = models.DecimalField(max_digits=12, decimal_places=2)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_at']

# NEW: Automatically logs data whenever AccountBalance updates
@receiver(post_save, sender=AccountBalance)
def create_account_history(sender, instance, created, **kwargs):
    # This automatically tracks changes when you save via forms or signals
    AccountHistory.objects.create(
        account=instance,
        balance_snapshot=instance.balance
    )



