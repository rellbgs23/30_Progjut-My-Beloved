from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from auth_app.decorators import staff_role_required

from .forms import PaymentForm
from .models import Invoice, Payment


@login_required
@staff_role_required("CASHIER")
def cashier_dashboard(request):
    """Halaman utama kasir: ringkasan invoice pending + shortcut ke payment."""

    unpaid_qs = Invoice.objects.filter(status=Invoice.InvoiceStatus.UNPAID)

    unpaid_invoices = (
        unpaid_qs.select_related("encounter__patient")
        .order_by("-createdAt")[:10]
    )

    unpaid_total = unpaid_qs.aggregate(total=Sum("totalAmount"))["total"] or 0

    todays_payments_total = Payment.objects.filter(
        processedBy__user=request.user,
        paidAt__date=timezone.localdate(),
    ).aggregate(total=Sum("paidAmount"))["total"] or 0

    return render(
        request,
        "billing_app/cashier_dashboard.html",
        {
            "unpaid_invoices": unpaid_invoices,
            "unpaid_count": unpaid_qs.count(),
            "unpaid_total": unpaid_total,
            "todays_payments_total": todays_payments_total,
            "active_nav": "dashboard",
        },
    )


@login_required
@staff_role_required("CASHIER")
def process_payment(request):
    """Cashier view untuk mencatat pembayaran terhadap invoice UNPAID.

    Keamanan:
    - @login_required + @staff_role_required("CASHIER").
    - `processedBy` di-inject dari request.user (tidak ada di form) sehingga
      identitas kasir tidak dapat di-spoof dari payload POST.
    - Transaksi di-wrap dalam transaction.atomic() + select_for_update pada
      invoice agar dua pembayaran konkuren tidak bisa sama-sama "lolos"
      cek sisa tagihan dan over-pay invoice.
    """

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save(commit=False)

                    # Lock invoice untuk durasi transaksi, lalu re-check
                    # sisa tagihan dari sumber truth (DB) sesudah lock.
                    invoice = Invoice.objects.select_for_update().get(
                        pk=payment.invoice_id
                    )

                    if invoice.status != Invoice.InvoiceStatus.UNPAID:
                        raise ValidationError(
                            "Invoice sudah tidak berstatus UNPAID."
                        )

                    current_total = invoice.payment_set.aggregate(
                        total=Sum("paidAmount")
                    )["total"] or 0
                    if current_total + payment.paidAmount > invoice.totalAmount:
                        raise ValidationError(
                            "Nominal melebihi sisa tagihan."
                        )

                    # Anti-spoofing: identitas kasir selalu dari sesi login.
                    payment.processedBy = request.user.staff
                    payment.invoice = invoice
                    payment.recordPayment()

                    new_total = current_total + payment.paidAmount
                    if new_total == invoice.totalAmount:
                        invoice.markAsPaid()
                        messages.success(
                            request,
                            f"Pembayaran berhasil. Invoice {invoice.id} lunas.",
                        )
                    else:
                        messages.success(
                            request,
                            "Pembayaran dicatat. Masih ada sisa tagihan.",
                        )

                return redirect("billing_app:process_payment")

            except ValidationError as error:
                messages.error(request, "; ".join(error.messages))
    else:
        form = PaymentForm()

    return render(
        request,
        "billing_app/payment_form.html",
        {"form": form, "active_nav": "payment"},
    )
