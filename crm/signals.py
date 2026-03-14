from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Deal, Contact, Task, Activity

_deal_stage_cache = {}


# ---------------------------------------------------------------------------
# Deal signals
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Deal)
def cache_deal_stage(sender, instance, **kwargs):
    if instance.pk:
        try:
            _deal_stage_cache[instance.pk] = Deal.objects.get(pk=instance.pk).stage
        except Deal.DoesNotExist:
            pass


@receiver(post_save, sender=Deal)
def on_deal_saved(sender, instance, created, **kwargs):
    from .services.ai_logic import compute_health_score, compute_close_probability

    # Log stage change
    if not created:
        old_stage = _deal_stage_cache.pop(instance.pk, None)
        if old_stage and old_stage != instance.stage:
            old_label = dict(Deal.STAGE_CHOICES).get(old_stage, old_stage)
            new_label = instance.get_stage_display()
            Activity.objects.create(
                type="stage_change",
                subject=f'Stage changed from "{old_label}" to "{new_label}"',
                deal=instance,
                owner=instance.owner,
                is_system=True,
            )

    # Recompute health score + close probability (use update() to avoid recursion)
    score = compute_health_score(instance)
    prob = compute_close_probability(instance, score)
    Deal.objects.filter(pk=instance.pk).update(health_score=score, close_probability=prob)


# ---------------------------------------------------------------------------
# Contact signals
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task signals
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Activity signals — sentiment + at-risk + health recompute
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Activity)
def on_activity_saved(sender, instance, created, **kwargs):
    if instance.is_system:
        return  # skip auto-generated entries

    from .services.ai_logic import analyze_sentiment, check_at_risk, compute_health_score, compute_close_probability

    text = f"{instance.body} {instance.transcript}".strip()

    # 1. Compute and store sentiment (use update() to avoid re-triggering this signal)
    sentiment = analyze_sentiment(text)
    Activity.objects.filter(pk=instance.pk).update(sentiment=sentiment)

    # 2. Flag linked deal as at-risk if risk keywords detected
    if instance.deal_id and check_at_risk(text):
        deal = Deal.objects.get(pk=instance.deal_id)
        if not deal.at_risk:
            Deal.objects.filter(pk=instance.deal_id).update(at_risk=True)
            Activity.objects.create(
                type="note",
                subject="⚠️ Deal flagged At Risk based on recent communication",
                deal=deal,
                owner=instance.owner,
                is_system=True,
            )

    # 3. Recompute health score for linked deal
    if instance.deal_id:
        fresh_deal = Deal.objects.get(pk=instance.deal_id)
        score = compute_health_score(fresh_deal)
        prob = compute_close_probability(fresh_deal, score)
        Deal.objects.filter(pk=instance.deal_id).update(health_score=score, close_probability=prob)
