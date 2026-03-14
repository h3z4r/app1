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
    employee_count = models.IntegerField(null=True, blank=True)
    linkedin_url = models.URLField(blank=True)
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
    whatsapp_number = models.CharField(max_length=50, blank=True)
    linkedin_profile_url = models.URLField(blank=True)
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
        ("nurture", "Nurture"),
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
    health_score = models.IntegerField(default=50)
    close_probability = models.IntegerField(default=10)
    at_risk = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)  # human-in-the-loop flag
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="deals")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def health_color(self):
        if self.health_score >= 70:
            return "green"
        if self.health_score >= 40:
            return "orange"
        return "red"

    @property
    def is_high_value(self):
        return float(self.value) > 50_000


class Activity(models.Model):
    TYPE_CHOICES = [
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("note", "Note"),
        ("task", "Task"),
        ("stage_change", "Stage Change"),
        ("voice_note", "Voice Note"),
    ]
    SENTIMENT_CHOICES = [
        ("positive", "Positive"),
        ("neutral", "Neutral"),
        ("concerned", "Concerned"),
    ]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    due_date = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="activities")

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return f"{self.get_type_display()} - {self.subject}"


class Task(models.Model):
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    STATUS_CHOICES = [("todo", "To Do"), ("in_progress", "In Progress"), ("done", "Done")]

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
        if not self.due_date or self.status == "done":
            return "ok"
        today = timezone.now().date()
        delta = (self.due_date - today).days
        if delta < 0:
            return "overdue"
        if delta <= 3:
            return "soon"
        return "ok"


# ── V4 Models ────────────────────────────────────────────────────────────────

class AuditLog(models.Model):
    """Every AI-agent action is recorded here (EU AI Act compliance)."""
    SOURCE_CHOICES = [
        ("user", "User"),
        ("ai_agent", "AI Agent"),
        ("system", "System"),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="user")
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=50)
    object_id = models.IntegerField()
    object_str = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_logs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.source}] {self.action} on {self.object_type} #{self.object_id}"


class SuggestedChange(models.Model):
    """Human-in-the-loop approval queue for high-value AI suggestions."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="suggested_changes")
    change_type = models.CharField(max_length=50)
    current_value = models.CharField(max_length=255)
    suggested_value = models.CharField(max_length=255)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="suggested_changes")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Suggested {self.change_type} for {self.deal}: {self.current_value} → {self.suggested_value}"


class InboxMessage(models.Model):
    """Unified Inbox — aggregates WhatsApp, Email, and CRM notes."""
    SOURCE_CHOICES = [
        ("whatsapp", "WhatsApp"),
        ("email", "Email"),
        ("crm_note", "CRM Note"),
    ]
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="inbound")
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="inbox_messages")
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    read = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inbox_messages")

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"[{self.source}] {self.subject or self.body[:50]}"


class AgentRun(models.Model):
    """Records each autonomous agent execution."""
    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("error", "Error"),
    ]
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_runs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    actions_taken = models.IntegerField(default=0)
    summary = models.TextField(blank=True)
    ran_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ran_at"]

    def __str__(self):
        return f"AgentRun {self.ran_at} ({self.status})"
