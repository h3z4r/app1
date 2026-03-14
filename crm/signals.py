from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Deal, Contact, Task, Activity

# Cache old deal stage before save so we can compare after
_deal_stage_cache = {}


@receiver(pre_save, sender=Deal)
def cache_deal_stage(sender, instance, **kwargs):
    if instance.pk:
        try:
            _deal_stage_cache[instance.pk] = Deal.objects.get(pk=instance.pk).stage
        except Deal.DoesNotExist:
            pass


@receiver(post_save, sender=Deal)
def log_deal_stage_change(sender, instance, created, **kwargs):
    if created:
        return
    old_stage = _deal_stage_cache.pop(instance.pk, None)
    if old_stage and old_stage != instance.stage:
        old_label = dict(Deal.STAGE_CHOICES).get(old_stage, old_stage)
        new_label = instance.get_stage_display()
        Activity.objects.create(
            type="stage_change",
            subject=f"Stage changed from \"{old_label}\" to \"{new_label}\"",
            deal=instance,
            owner=instance.owner,
            is_system=True,
        )


@receiver(post_save, sender=Contact)
def log_contact_update(sender, instance, created, **kwargs):
    if not created:
        Activity.objects.create(
            type="note",
            subject="Contact information updated",
            contact=instance,
            owner=instance.owner,
            is_system=True,
        )


@receiver(post_save, sender=Task)
def log_task_created(sender, instance, created, **kwargs):
    if created:
        Activity.objects.create(
            type="task",
            subject=f"Task created: {instance.title}",
            contact=instance.contact,
            deal=instance.deal,
            owner=instance.owner,
            is_system=True,
        )
