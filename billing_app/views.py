from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from decimal import Decimal
from .forms import PaymentForm
from .models import Invoice, Payment


def is_cashier(user):
    return hasattr(user, 'staff') and user.staff.role == 'CASHIER'


@login_required
@user_passes_test(is_cashier, login_url='/auth/denied/')
def invoice_list(request):
    query = request.GET.get('q', '')
    # Default nampilin UNPAID sesuai request lu
    status_filter = request.GET.get('status', 'UNPAID')

    # Sort by time (-createdAt) default dari backend
    invoices = Invoice.objects.select_related(
        'encounter__patient').all().order_by('-createdAt')

    # Filter by Status
    if status_filter in ['UNPAID', 'PAID']:
        invoices = invoices.filter(status=status_filter)

    # Filter by Search Query
    if query:
        invoices = invoices.filter(
            Q(id__icontains=query) |
            Q(encounter__patient__name__icontains=query) |
            Q(encounter__patient__mrn__icontains=query)
        )

    return render(request, 'billing_app/invoice_list.html', {
        'invoices': invoices,
        'query': query,
        'current_status': status_filter
    })


@login_required
@user_passes_test(is_cashier, login_url='/auth/denied/')
def invoice_pay(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)
    payments = invoice.payment_set.all().order_by('-paidAt')

    current_payments = sum((p.paidAmount for p in payments), Decimal('0.00'))
    remaining_balance = invoice.totalAmount - current_payments

    if request.method == 'POST':
        form = PaymentForm(request.POST, invoice=invoice)

        # FIX ERROR: Inject invoice ke dalam instance form SEBELUM form divoalidasi!
        form.instance.invoice = invoice

        if form.is_valid():
            try:
                payment = form.save(commit=False)
                # Invoice udah aman, tinggal inject kasir
                payment.processedBy = request.user.staff
                payment.recordPayment()

                new_total = current_payments + payment.paidAmount
                if new_total >= invoice.totalAmount:
                    invoice.markAsPaid()
                    messages.success(
                        request, f"LUNAS! Invoice berstatus PAID.")
                    return redirect('billing_app:invoice_list')
                else:
                    messages.success(
                        request, f"Pembayaran Rp{payment.paidAmount} dicatat. Sisa tagihan di-update.")
                    return redirect('billing_app:invoice_pay', invoice_id=invoice.id)

            except ValidationError as e:
                # Tangkap error OCL dari model kalau ada
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.error(request, err)
                else:
                    for err in e.messages:
                        messages.error(request, err)
        else:
            # Looping untuk ngeluarin semua error spesifik dari form
            for field, errors in form.errors.items():
                for error in errors:
                    # Kalau errornya nempel di specific field (misal paidAmount)
                    if field != '__all__':
                        messages.error(request, f"{error}")
                    else:
                        messages.error(request, error)
    else:
        form = PaymentForm(invoice=invoice)

    context = {
        'invoice': invoice,
        'form': form,
        'remaining_balance': remaining_balance,
        'payments': payments,
    }
    return render(request, 'billing_app/invoice_pay.html', context)
