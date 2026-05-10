from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from decimal import Decimal
from .forms import PaymentForm, InvoiceForm
from .models import Invoice, Payment, Encounter


def is_cashier(user):
    return hasattr(user, 'staff') and user.staff.role == 'CASHIER'


@login_required
@user_passes_test(is_cashier, login_url='/auth/denied/')
def invoice_list(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', 'UNPAID')

    invoices = Invoice.objects.select_related('encounter__patient').prefetch_related(
        'payment_set').all().order_by('-createdAt')

    if status_filter in ['UNPAID', 'PAID']:
        invoices = invoices.filter(status=status_filter)

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

        form.instance.invoice = invoice

        if form.is_valid():
            try:
                payment = form.save(commit=False)
                payment.processedBy = request.user.staff
                payment.recordPayment()

                new_total = current_payments + payment.paidAmount
                if new_total >= invoice.totalAmount:
                    invoice.markAsPaid()
                    messages.success(
                        request, f"LUNAS! Invoice berstatus PAID.")
                    return redirect('billing_app:invoice_pay', invoice_id=invoice.id)
                else:
                    messages.success(
                        request, f"Pembayaran Rp{payment.paidAmount} dicatat. Sisa tagihan di-update.")
                    return redirect('billing_app:invoice_pay', invoice_id=invoice.id)

            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for err in errors:
                            messages.error(request, err)
                else:
                    for err in e.messages:
                        messages.error(request, err)
        else:
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


@login_required
@user_passes_test(is_cashier, login_url='/auth/denied/')
def create_invoice(request):
    available_encounters = Encounter.objects.filter(invoice__isnull=True)
    if not available_encounters.exists():
        return render(request, 'billing_app/create_invoice.html', {'no_encounters': True})

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            try:
                invoice = form.save()

                if invoice.totalAmount == Decimal('0.00'):
                    invoice.markAsPaid()
                    messages.success(
                        request, f"Tagihan Rp0 untuk {invoice.encounter.patient.name} otomatis LUNAS.")
                else:
                    messages.success(
                        request, f"Berhasil! Tagihan untuk {invoice.encounter.patient.name} telah dibuat.")

                return redirect('billing_app:invoice_list')
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    if field != '__all__':
                        messages.error(request, f"{error}")
                    else:
                        messages.error(request, error)
    else:
        form = InvoiceForm()

    return render(request, 'billing_app/create_invoice.html', {'form': form, 'no_encounters': False})
