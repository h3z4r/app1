from django import forms
from .models import Company, Contact, Deal, Activity


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "website", "phone", "email", "address", "industry"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "email", "phone", "company", "job_title", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = ["title", "contact", "company", "value", "stage", "close_date", "notes"]
        widgets = {
            "close_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["type", "subject", "body", "contact", "deal", "due_date", "completed"]
        widgets = {
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "body": forms.Textarea(attrs={"rows": 3}),
        }
