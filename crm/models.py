from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Company(models.Model):
    name = models.CharField(max_length=255)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="companies")

    class Meta:
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="contacts")
    job_title = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="contacts")

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Deal(models.Model):
    STAGE_CHOICES = [
        ("lead", "Lead"),
        ("qualified", "Qualified"),
        ("proposal", "Proposal"),
        ("negotiation", "Negotiation"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    title = models.CharField(max_length=255)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="deals")
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="lead")
    close_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="deals")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Activity(models.Model):
    TYPE_CHOICES = [
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("note", "Note"),
        ("task", "Task"),
        ("stage_change", "Stage Change"),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    due_date = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)  # True = auto-logged by signals
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="activities")

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.get_type_display()} - {self.subject}"


class Task(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("todo", "To Do"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo")
    due_date = models.DateField(null=True, blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="tasks")

    class Meta:
        ordering = ["due_date", "-priority"]

    def __str__(self):
        return self.title

    @property
    def due_status(self):
        """Returns 'overdue', 'soon', or 'ok' based on due_date."""
        if not self.due_date or self.status == "done":
            return "ok"
        today = timezone.now().date()
        delta = (self.due_date - today).days
        if delta < 0:
            return "overdue"
        if delta <= 3:
            return "soon"
        return "ok"
