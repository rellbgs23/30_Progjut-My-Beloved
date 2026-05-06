from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from .forms import PaymentForm


def is_cashier(user):
    return hasattr(user, 'staff') and user.staff.role == 'CASHIER'

# kick user yang belum login (CWE-287)
# atau user yang login tapi bukan Kasir (CWE-862)
@login_required
@user_passes_test(is_cashier, login_url='/auth/denied/') # TODO: bikin hal. access denied
def process_payment(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                # jangan langsung di-save ke database dulu (commit=False)
                payment = form.save(commit=False)

                # Anti-Spoofing & Non-repudiation: Identitas kasir diisi otomatis oleh sistem dari sesi login (request.user),
                # bukan dari input form yang bisa dimanipulasi Attacker.
                payment.processedBy = request.user.staff

                # membuat AuditLog
                payment.recordPayment()

                # cek apakah Invoice sudah lunas
                invoice = payment.invoice
                total_payments = sum(
                    p.paidAmount for p in invoice.payment_set.all())

                if total_payments == invoice.totalAmount:
                    # jika total bayar sudah pas dengan tagihan, ubah status jadi PAID
                    invoice.markAsPaid()
                    messages.success(
                        request, f"Pembayaran berhasil diproses. Invoice {invoice.id} berstatus PAID.")
                else:
                    messages.success(
                        request, f"Pembayaran berhasil dicatat. Sisa tagihan masih menunggu.")

                return redirect('process_payment')  # refresh halaman

            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = PaymentForm()

    return render(request, 'billing_app/payment_form.html', {'form': form})
