from django import forms
from .models import Company, Contact, Deal, Activity, Task


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "website", "phone", "email", "address", "industry", "employee_count", "linkedin_url"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["first_name", "last_name", "email", "phone", "whatsapp_number", "linkedin_profile_url", "company", "job_title", "notes"]
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
        fields = ["type", "subject", "body", "transcript", "contact", "company", "deal", "due_date", "completed"]
        widgets = {
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "body": forms.Textarea(attrs={"rows": 3}),
            "transcript": forms.Textarea(attrs={"rows": 5, "placeholder": "Paste meeting transcript here — sentiment will be analysed automatically..."}),
        }


class NoteForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Add a note..."}),
        label="",
    )


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "priority", "status", "due_date", "contact", "deal"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
