from django.db import models


class MemoryType(models.TextChoices):
    PREFERENCE = "preference", "Preference"
    FACT = "fact", "Fact"
    HISTORY_SUMMARY = "history_summary", "History Summary"


class UserProfile(models.Model):
    """
    Minimal user model for the agent.
    You can also link to Django auth.User if you want.
    """
    id = models.CharField(primary_key=True, max_length=64)  # e.g. "user-123"
    display_name = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserMemory(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="memories")
    type = models.CharField(max_length=32, choices=MemoryType.choices)
    content = models.TextField()
    importance = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ConversationSession(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)


class ConversationEvent(models.Model):
    session = models.ForeignKey(ConversationSession, on_delete=models.CASCADE, related_name="events")
    role = models.CharField(max_length=32)  # "user" or "assistant"
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
