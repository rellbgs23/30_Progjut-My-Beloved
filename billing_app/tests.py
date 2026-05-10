from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from datetime import date
from auth_app.models import UserAccount, Staff
from medical_app.models import Patient, Encounter
from billing_app.models import Invoice


class BillingSecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        self.cashier_user = UserAccount.objects.create_user(
            username='cashier_test', password='hitam123')
        self.cashier_staff = Staff.objects.create(
            user=self.cashier_user, name='Cashier 1', role='CASHIER')

        self.doctor_user = UserAccount.objects.create_user(
            username='doctor_test', password='hitam123')
        self.doctor_staff = Staff.objects.create(
            user=self.doctor_user, name='Doctor 1', role='DOCTOR')

        self.patient_user = UserAccount.objects.create_user(
            username='patient_test', password='hitam123', is_patient=True)
        self.patient = Patient.objects.create(
            user=self.patient_user,
            mrn='MRN-001',
            name='Pasien Test',
            dateOfBirth=date(1990, 1, 1),
            address='Jl. Testing No. 1',
            phoneNumber='081234567890'
        )

        self.encounter = Encounter.objects.create(
            patient=self.patient, staff=self.doctor_staff, complaint='Sakit')
        self.invoice = Invoice.objects.create(
            encounter=self.encounter, totalAmount=Decimal('50000.00'), status='UNPAID')

        self.list_url = reverse('billing_app:invoice_list')
        self.create_url = reverse('billing_app:create_invoice')

        self.pay_url = reverse('billing_app:invoice_pay',
                               args=[self.invoice.pk])

    def test_sqli_prevention_on_search(self):
        self.client.login(username='cashier_test', password='hitam123')
        response = self.client.get(
            self.list_url, {'q': "'; DROP TABLE billing_app_invoice; --"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tidak ada tagihan ditemukan.")

    def test_xss_prevention_on_search(self):
        self.client.login(username='cashier_test', password='hitam123')
        response = self.client.get(
            self.list_url, {'q': "<script>alert(1)</script>"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_payment_minimum_amount_validation(self):
        self.client.login(username='cashier_test', password='hitam123')
        response = self.client.post(
            self.pay_url, {'paidAmount': '-5000.00', 'method': 'CASH'})
        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response, 'Nominal pembayaran minimal adalah Rp 1.000!')

    def test_payment_overpayment_validation(self):
        self.client.login(username='cashier_test', password='hitam123')
        response = self.client.post(
            self.pay_url, {'paidAmount': '60000.00', 'method': 'CASH'})
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'Nominal kelebihan!')

    def test_invoice_creation_zero_amount_auto_paid(self):
        self.client.login(username='cashier_test', password='hitam123')
        encounter_zero = Encounter.objects.create(
            patient=self.patient, staff=self.doctor_staff, complaint='Gratis')

        response = self.client.post(
            self.create_url, {'encounter': encounter_zero.pk, 'totalAmount': '0.00'})
        self.assertEqual(response.status_code, 302)

        invoice_zero = Invoice.objects.get(encounter=encounter_zero)
        self.assertEqual(invoice_zero.status, 'PAID')

    def test_unauthenticated_access_redirects_to_login(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/auth/'))

    def test_least_privilege_doctor_denied(self):
        self.client.login(username='doctor_test', password='hitam123')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(response.url.startswith('/auth/denied/'))

    def test_least_privilege_patient_denied(self):
        self.client.login(username='patient_test', password='hitam123')
        response = self.client.get(self.pay_url)
        self.assertEqual(response.status_code, 302)

        self.assertTrue(response.url.startswith('/auth/denied/'))

    def test_csrf_protection_on_payment(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='cashier_test', password='hitam123')
        response = csrf_client.post(
            self.pay_url, {'paidAmount': '50000.00', 'method': 'CASH'})
        self.assertEqual(response.status_code, 403)

    def test_csrf_protection_on_create_invoice(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='cashier_test', password='hitam123')

        response = csrf_client.post(
            self.create_url, {'encounter': self.encounter.pk, 'totalAmount': '10000.00'})
        self.assertEqual(response.status_code, 403)
