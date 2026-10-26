from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Expense


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


class ExpenseAjaxEditTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(username='edit-user', password='test-pass')
		self.client.force_login(self.user)
		self.category = Category.objects.create(
			user=self.user,
			name='Food',
		)
		self.expense = Expense.objects.create(
			user=self.user,
			amount='30.00',
			date=date(2026, 1, 1),
			description='Lunch',
			category=self.category,
		)

	def test_ajax_edit_returns_updated_expense_data(self):
		response = self.client.post(
			reverse('expenses:edit_expense_dashboard', args=[self.expense.pk]),
			{
				'amount': '45.50',
				'category': self.category.pk,
				'date': '2026-01-02',
				'description': 'Dinner',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['status'], 'success')
		self.assertEqual(response.json()['expense']['description'], 'Dinner')
		self.assertEqual(response.json()['expense']['raw_amount'], '45.50')
		self.expense.refresh_from_db()
		self.assertEqual(self.expense.description, 'Dinner')

	def test_edit_button_renders_large_amount_without_grouping_separator(self):
		self.expense.amount = '1234.56'
		self.expense.save()

		response = self.client.get(reverse('expenses:home'), {'timeframe': 'all'})

		self.assertContains(response, 'data-amount="1234.56"')
		self.assertNotContains(response, 'data-amount="1,234.56"')
