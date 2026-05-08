from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        # invoice sengaja ga dimasukkan karena sudah di-handle via URL di views.py
        fields = ['paidAmount', 'method']

        widgets = {
            # min diganti jadi 1000 buat UI di HTML
            'paidAmount': forms.NumberInput(attrs={'class': 'form-control', 'min': '1000', 'step': '1'}),
            'method': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Ambil instance 'invoice' yang dilempar dari views.py (kalau ada)
        # Hapus dari kwargs biar nggak error saat manggil super()
        self.invoice_instance = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)

        self.fields['paidAmount'].label = "Nominal Pembayaran (Rp)"
        self.fields['method'].label = "Metode Pembayaran"

    def clean_paidAmount(self):
        paid_amount = self.cleaned_data.get('paidAmount')

        # Aturan baru: validasi minimal bayar Rp 1.000
        if paid_amount is None or paid_amount < Decimal('1000.00'):
            raise ValidationError(
                "Nominal pembayaran minimal adalah Rp 1.000!")

        return paid_amount

    def clean(self):
        cleaned_data = super().clean()
        paid_amount = cleaned_data.get('paidAmount')

        # Cek sisa tagihan langsung di dalam form pakai invoice_instance
        if paid_amount and self.invoice_instance:
            current_payments = sum(
                (p.paidAmount for p in self.invoice_instance.payment_set.all()), Decimal(
                    '0.00')
            )
            remaining_balance = self.invoice_instance.totalAmount - current_payments

            if paid_amount > remaining_balance:
                self.add_error(
                    'paidAmount',
                    f"Nominal kelebihan! Sisa tagihan ini cuma Rp{remaining_balance}."
                )

        return cleaned_data
