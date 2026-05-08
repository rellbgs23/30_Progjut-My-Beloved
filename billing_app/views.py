from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from .forms import PaymentForm


def is_cashier(user):
    return (
        user.is_authenticated
        and hasattr(user, "staff")
        and user.staff.role == "CASHIER"
    )


@login_required
@user_passes_test(is_cashier, login_url="/auth/denied/")
def process_payment(request):
    """Cashier view untuk mencatat pembayaran terhadap invoice UNPAID.

    Keamanan:
    - @login_required + @user_passes_test(is_cashier): CWE-287 & CWE-862.
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
                    from .models import Invoice  # lokal untuk hindari circular

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
                            f"Pembayaran berhasil diproses. Invoice {invoice.id} berstatus PAID.",
                        )
                    else:
                        messages.success(
                            request,
                            "Pembayaran berhasil dicatat. Sisa tagihan masih menunggu.",
                        )

                return redirect("billing_app:process_payment")

            except ValidationError as error:
                # ValidationError bisa punya atribut yang berbeda-beda
                # (message / messages / message_dict). Ambil versi string
                # yang paling aman untuk ditampilkan ke user.
                messages.error(request, "; ".join(error.messages))
    else:
        form = PaymentForm()

    return render(request, "billing_app/payment_form.html", {"form": form})
