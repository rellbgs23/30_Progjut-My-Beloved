import uuid
import hashlib
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from auth_app.models import Staff
from medical_app.models import Encounter


class Invoice(models.Model):
    class InvoiceStatus(models.TextChoices):
        UNPAID = 'UNPAID', 'Unpaid'
        PAID = 'PAID', 'Paid'
        VOID = 'VOID', 'Void'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE)

    # CWE-20: mencegah tagihan bernilai negatif, tapi tetap membolehkan 0 (untuk dokumentasi [ex: subsidi])
    totalAmount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.UNPAID)
    createdAt = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        # OCL: ExactPaymentForPaidStatus
        if self.status == self.InvoiceStatus.PAID:
            total_payments = self.payment_set.aggregate(
                total=models.Sum('paidAmount')
            )['total'] or Decimal('0.00')

            if total_payments != self.totalAmount:
                raise ValidationError(
                    "Invoice cannot be PAID if total payments do not match totalAmount.")

        # OCL: VoidMeansNoPayments
        if self.status == self.InvoiceStatus.VOID:
            if self.payment_set.exists():
                raise ValidationError(
                    "Invoice cannot be VOID because it already has associated payments.")

    def markAsPaid(self):
        self.status = self.InvoiceStatus.PAID
        self.full_clean()
        self.save()

    def voidInvoice(self):
        self.status = self.InvoiceStatus.VOID
        self.full_clean()
        self.save()

    def __str__(self):
        return f"Invoice {self.id} - {self.status}"


class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        DEBIT = 'DEBIT', 'Debit'
        TRANSFER = 'TRANSFER', 'Transfer'
        QRIS = 'QRIS', 'Qris'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.RESTRICT)

    # OCL: ProcessedByCashier
    processedBy = models.ForeignKey(
        Staff,
        on_delete=models.RESTRICT,
        limit_choices_to={'role': 'CASHIER'}
    )

    # OCL: PositiveAmount (Pembayaran harus benar-benar lebih dari nol)
    paidAmount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    paidAt = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()

        # OCL: InvoiceMustBeUnpaid
        if self.invoice.status != Invoice.InvoiceStatus.UNPAID:
            raise ValidationError(
                "Payments can only be recorded for UNPAID invoices.")

        current_payments = self.invoice.payment_set.aggregate(
            total=models.Sum('paidAmount')
        )['total'] or Decimal('0.00')

        # cek apakah uang yang mau dibayar sekarang bikin totalnya melebihi tagihan
        if current_payments + self.paidAmount > self.invoice.totalAmount:
            raise ValidationError(
                f"Invalid Payment: Amount exceeds the remaining invoice total. "
                f"Remaining balance is {self.invoice.totalAmount - current_payments}."
            )

    def recordPayment(self):
        self.full_clean()
        self.save()

        # OCL: AuditLogExists
        AuditLog.objects.create(
            payment=self,
            action=f"Payment {self.method} of {self.paidAmount} recorded for Invoice {self.invoice.id}"
        )

    def __str__(self):
        return f"Payment {self.id} for Invoice {self.invoice.id}"


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.RESTRICT)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255)

    # Cryptographic Log Integrity
    hash = models.CharField(max_length=64, editable=False)

    def save(self, *args, **kwargs):
        if not self.hash:
            last_log = AuditLog.objects.order_by('-timestamp').first()
            previous_hash = last_log.hash if last_log else "GENESIS_BLOCK"
            data_to_hash = f"{self.action}|{self.payment.id}|{previous_hash}".encode(
                'utf-8')
            self.hash = hashlib.sha256(data_to_hash).hexdigest()
        super().save(*args, **kwargs)

    def recordAction(self, action_desc):
        self.action = action_desc
        self.save()

    def __str__(self):
        return f"Log {self.id} - {self.action}"
