from django.contrib import admin
from .models import Company, Contact, Deal, Activity


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "phone", "email", "owner", "created_at")
    search_fields = ("name", "industry", "email")
    list_filter = ("industry", "owner")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "company", "job_title", "owner")
    search_fields = ("first_name", "last_name", "email", "phone")
    list_filter = ("company", "owner")


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("title", "contact", "company", "value", "stage", "close_date", "owner")
    search_fields = ("title",)
    list_filter = ("stage", "owner")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("subject", "type", "contact", "deal", "due_date", "completed", "owner")
    search_fields = ("subject", "body")
    list_filter = ("type", "completed", "owner")
