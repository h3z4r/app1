"""
Management command: python manage.py run_agent

Runs the autonomous sales agent for all active users.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from crm.agents.sales_agent import run_sales_agent
from crm.models import AgentRun


class Command(BaseCommand):
    help = "Run the autonomous sales agent for all active users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Run only for a specific username",
        )

    def handle(self, *args, **options):
        users = User.objects.filter(is_active=True)
        if options.get("user"):
            users = users.filter(username=options["user"])

        for user in users:
            self.stdout.write(f"Running agent for {user.username}...")
            agent_run = AgentRun.objects.create(owner=user, status="running")
            try:
                result = run_sales_agent(user)
                total = len(result["actions"]) + len(result["suggested"])
                agent_run.status = "completed"
                agent_run.actions_taken = total
                agent_run.summary = "\n".join(result["actions"] + result["suggested"])
                agent_run.save()

                for msg in result["actions"]:
                    self.stdout.write(f"  ✓ {msg}")
                for msg in result["suggested"]:
                    self.stdout.write(f"  ⚑ {msg}")
                self.stdout.write(
                    self.style.SUCCESS(f"  Done — {total} action(s) for {user.username}")
                )
            except Exception as e:
                agent_run.status = "error"
                agent_run.summary = str(e)
                agent_run.save()
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))
