from django import forms


class PrescriptionItemForm(forms.Form):
    itemId = forms.CharField(max_length=50)
    medicineName = forms.CharField(max_length=200)
    dosage = forms.CharField(max_length=100)
    quantity = forms.IntegerField(min_value=1)
    instruction = forms.CharField(max_length=1000)

    def clean_itemId(self):
        value = self.cleaned_data['itemId'].strip()
        if not value:
            raise forms.ValidationError('Item ID is required.')
        return value

    def clean_medicineName(self):
        value = self.cleaned_data['medicineName'].strip()
        if not value:
            raise forms.ValidationError('Medicine name is required.')
        return value

    def clean_dosage(self):
        value = self.cleaned_data['dosage'].strip()
        if not value:
            raise forms.ValidationError('Dosage is required.')
        return value

    def clean_instruction(self):
        return self.cleaned_data['instruction'].strip()
