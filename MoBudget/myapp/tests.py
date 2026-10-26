from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Expense


class ExpenseAmountSortingTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='sort-user', password='test-pass')
		self.client.force_login(self.user)
		Expense.objects.create(user=self.user, amount='30.00', date=date(2026, 1, 1), description='Higher')
		Expense.objects.create(user=self.user, amount='10.00', date=date(2026, 1, 2), description='Lower')

	def test_expense_list_sorts_amount_ascending_and_descending(self):
		url = reverse('expenses:home')

		ascending = self.client.get(url, {'timeframe': 'all', 'sort': 'amount', 'direction': 'asc'})
		descending = self.client.get(url, {'timeframe': 'all', 'sort': 'amount', 'direction': 'desc'})

		self.assertEqual(ascending.status_code, 200)
		self.assertEqual(descending.status_code, 200)
		self.assertEqual([expense.amount for expense in ascending.context['expenses']], [10, 30])
		self.assertEqual([expense.amount for expense in descending.context['expenses']], [30, 10])
		self.assertEqual(ascending.context['next_amount_direction'], 'desc')
		self.assertEqual(descending.context['next_amount_direction'], 'asc')
