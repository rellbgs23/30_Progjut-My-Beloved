from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from .models import Payment, Invoice


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        # tidak usah memasukkan 'processedBy' ke sini untuk mencegah Spoofing.
        # identitas kasir akan di-inject langsung di views.py berdasarkan request.user
        fields = ['invoice', 'paidAmount', 'method']

        widgets = {
            'paidAmount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'method': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # hanya tampilkan Invoice yang statusnya UNPAID di dropdown.
        # mencegah Kasir memproses tagihan yang sudah lunas atau dibatalkan.
        self.fields['invoice'].queryset = Invoice.objects.filter(
            status=Invoice.InvoiceStatus.UNPAID)
        self.fields['invoice'].widget.attrs.update({'class': 'form-control'})

        self.fields['invoice'].label = "Pilih Tagihan (UNPAID)"
        self.fields['paidAmount'].label = "Nominal Pembayaran (Rp)"
        self.fields['method'].label = "Metode Pembayaran"

    def clean_paidAmount(self):
        paid_amount = self.cleaned_data.get('paidAmount')

        # validasi tambahan di form untuk memastikan input tidak bernilai 0 atau negatif
        if paid_amount is None or paid_amount <= 0:
            raise ValidationError("Nominal pembayaran harus lebih dari 0!")

        return paid_amount

    def clean(self):
        cleaned_data = super().clean()
        paid_amount = cleaned_data.get('paidAmount')
        invoice = cleaned_data.get('invoice')

        if paid_amount and invoice:
            current_payments = sum(
                (p.paidAmount for p in invoice.payment_set.all()), Decimal('0.00')
            )
            remaining_balance = invoice.totalAmount - current_payments

            if paid_amount > remaining_balance:
                self.add_error(
                    'paidAmount',
                    f"Nominal kelebihan! Sisa tagihan ini cuma Rp{remaining_balance}."
                )

        return cleaned_data
