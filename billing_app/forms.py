from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import Invoice, Payment


class PaymentForm(forms.ModelForm):
    """Form untuk mencatat pembayaran oleh kasir.

    Catatan keamanan penting:
    - Field `processedBy` sengaja TIDAK disertakan. Identitas kasir
      di-inject di `views.py` dari `request.user.staff` sehingga tidak
      dapat di-spoof lewat payload form.
    - Dropdown `invoice` dibatasi hanya invoice yang berstatus UNPAID
      agar kasir tidak bisa secara tidak sengaja (atau sengaja) memproses
      pembayaran untuk invoice PAID atau VOID.
    """

    class Meta:
        model = Payment
        fields = ["invoice", "paidAmount", "method"]

        widgets = {
            "paidAmount": forms.NumberInput(
                attrs={"min": "0.01", "step": "0.01"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["invoice"].queryset = Invoice.objects.filter(
            status=Invoice.InvoiceStatus.UNPAID
        ).order_by("-createdAt")

        self.fields["invoice"].label = "Tagihan (UNPAID)"
        self.fields["paidAmount"].label = "Nominal Pembayaran (Rp)"
        self.fields["method"].label = "Metode Pembayaran"

    def clean_paidAmount(self):
        paid_amount = self.cleaned_data.get("paidAmount")

        if paid_amount is None or paid_amount <= 0:
            raise ValidationError("Nominal pembayaran harus lebih dari 0.")

        return paid_amount

    def clean(self):
        cleaned_data = super().clean()
        paid_amount = cleaned_data.get("paidAmount")
        invoice = cleaned_data.get("invoice")

        if paid_amount and invoice:
            # Dihitung lewat aggregate() alih-alih sum(generator) supaya
            # tidak N+1 query dan lebih hemat memori ketika invoice punya
            # banyak payment. Cek otoritatif tetap di views.py dalam
            # transaksi dengan SELECT ... FOR UPDATE — cek di sini hanya
            # untuk feedback UI cepat.
            current_payments = invoice.payment_set.aggregate(
                total=Sum("paidAmount")
            )["total"] or Decimal("0.00")

            remaining_balance = invoice.totalAmount - current_payments

            if paid_amount > remaining_balance:
                self.add_error(
                    "paidAmount",
                    f"Nominal kelebihan. Sisa tagihan Rp{remaining_balance}.",
                )

        return cleaned_data
