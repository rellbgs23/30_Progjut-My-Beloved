from django.test import TestCase
from django.urls import reverse

from auth_app.models import Staff, UserAccount


class BillingNavbarTests(TestCase):
    def setUp(self):
        self.cashier_user = UserAccount.objects.create_user(
            username="cashier_nav",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(
            user=self.cashier_user,
            name="Cashier Nav",
            role="CASHIER",
        )

    def test_invoice_list_uses_shared_cashier_navbar(self):
        self.client.login(username="cashier_nav", password="StrongPassword123!")

        response = self.client.get(reverse("billing_app:invoice_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="app-navbar"')
        self.assertContains(response, reverse("billing_app:invoice_list"))
        self.assertContains(response, "Billing")
        self.assertContains(response, "cashier_nav")