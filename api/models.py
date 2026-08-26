from django.db import models
from django.contrib.auth.models import User
import calendar
import uuid

from django.core.exceptions import ValidationError
from django.utils import timezone



# ──────────────────────────────────────────────────────────────────────────────
# Celebrity
# ──────────────────────────────────────────────────────────────────────────────

class Celebrity(models.Model):
    # Identity
    name        = models.CharField(max_length=200)
    profession  = models.CharField(max_length=300)
    nationality = models.CharField(max_length=200)
    bio         = models.TextField(blank=True)

    # Birthday — keep both: birthdate (display string) + birth_date (filterable)
    birthdate  = models.CharField(max_length=50, blank=True)   # e.g. "April 23"
    birth_date = models.DateField(null=True, blank=True)        # for DB filtering

    # Visuals
    initials      = models.CharField(max_length=5, blank=True)
    gradient_from = models.CharField(max_length=20, default='#F5A623')
    gradient_to   = models.CharField(max_length=20, default='#E91E8C')
    image         = models.ImageField(upload_to='celebrities/', blank=True, null=True)

    # Meta
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Celebrities'

    def __str__(self):
        return self.name

    @property
    def age(self):
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return (
            today.year - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    @property
    def is_birthday_today(self):
        if not self.birth_date:
            return False
        from datetime import date
        today = date.today()
        return self.birth_date.month == today.month and self.birth_date.day == today.day


# ──────────────────────────────────────────────────────────────────────────────
# Article
# ──────────────────────────────────────────────────────────────────────────────

class Article(models.Model):
    CATEGORY_CHOICES = [
        ('birthday',   'Birthday'),
        ('sports',     'Sports'),
        ('love_story', 'Love Story'),
        ('charity',    'Charity'),
        ('general',    'General'),
    ]

    # Core content
    title    = models.CharField(max_length=300)
    excerpt  = models.TextField(blank=True)
    content  = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')

    # Relations
    author    = models.ForeignKey(User,      on_delete=models.SET_NULL, null=True)
    celebrity = models.ForeignKey(Celebrity, on_delete=models.SET_NULL, null=True, blank=True)

    # Media
    image = models.ImageField(upload_to='articles/',      blank=True, null=True)
    audio = models.FileField(upload_to='articles/audio/', blank=True, null=True)

    # Display metadata
    tag       = models.CharField(max_length=50, blank=True)
    tag_color = models.CharField(max_length=20, blank=True)

    # Engagement counters
    reads    = models.IntegerField(default=0)
    likes    = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares   = models.IntegerField(default=0)

    # Status & timestamps
    is_published    = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    is_editors_pick = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def read_time(self):
        if not self.content:
            return '1 min read'
        minutes = max(1, round(len(self.content.split()) / 200))
        return f'{minutes} min read'


# ──────────────────────────────────────────────────────────────────────────────
# Post
# ──────────────────────────────────────────────────────────────────────────────

class Post(models.Model):
    user    = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    image   = models.ImageField(upload_to='posts/', blank=True, null=True)

    tag       = models.CharField(max_length=50, blank=True)
    tag_color = models.CharField(max_length=20, blank=True)

    likes    = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares   = models.IntegerField(default=0)

    is_published = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}"


# ──────────────────────────────────────────────────────────────────────────────
# Charity
# ──────────────────────────────────────────────────────────────────────────────

class Charity(models.Model):
    title       = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    beneficiary = models.CharField(max_length=200, blank=True)
    location    = models.CharField(max_length=200, blank=True)

    goal   = models.DecimalField(max_digits=12, decimal_places=2)
    raised = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    donors = models.PositiveIntegerField(default=0)

    tag    = models.CharField(max_length=50, blank=True)
    avatar = models.CharField(max_length=5, blank=True)
    image  = models.ImageField(upload_to='charities/', blank=True, null=True)

    urgent    = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Charities'

    def __str__(self):
        return self.title

    @property
    def progress(self):
        if self.goal > 0:
            return round((float(self.raised) / float(self.goal)) * 100)
        return 0


# ──────────────────────────────────────────────────────────────────────────────
# Love Story
# ──────────────────────────────────────────────────────────────────────────────

class LoveStory(models.Model):
    title   = models.CharField(max_length=300)
    excerpt = models.TextField()
    content = models.TextField(blank=True)

    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    image  = models.ImageField(upload_to='love_stories/', blank=True, null=True)
    avatar = models.CharField(max_length=5, blank=True)

    # Denormalised counters — kept in sync by the view actions below
    likes    = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares   = models.IntegerField(default=0)

    is_published = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def read_time(self):
        if not self.content:
            return '1 min read'
        minutes = max(1, round(len(self.content.split()) / 200))
        return f'{minutes} min read'


# ──────────────────────────────────────────────────────────────────────────────
# Love Story — Like  (unique per user+story → no double-liking)
# ──────────────────────────────────────────────────────────────────────────────

class LoveStoryLike(models.Model):
    story      = models.ForeignKey(LoveStory, on_delete=models.CASCADE, related_name='story_likes')
    user       = models.ForeignKey(User,      on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['story', 'user']   # ← prevents duplicate likes
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ♥ {self.story.title}"


# ──────────────────────────────────────────────────────────────────────────────
# Love Story — Comment  (persisted text, fetchable after refresh)
# ──────────────────────────────────────────────────────────────────────────────

class LoveStoryComment(models.Model):
    story      = models.ForeignKey(LoveStory, on_delete=models.CASCADE, related_name='story_comments')
    user       = models.ForeignKey(User,      on_delete=models.CASCADE)
    text       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']   # oldest first inside the panel

    def __str__(self):
        return f"{self.user.username} on '{self.story.title}': {self.text[:40]}"


# ──────────────────────────────────────────────────────────────────────────────
# Subscription
# ──────────────────────────────────────────────────────────────────────────────

class Subscription(models.Model):
    subscriber = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscribers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['subscriber', 'author']
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.subscriber.username} → {self.author.username}"


# ──────────────────────────────────────────────────────────────────────────────
# Celebrant
# ──────────────────────────────────────────────────────────────────────────────

def celebrant_photo_path(instance, filename):
    # NOTE: don't use instance.id here — at upload time (on create), the row
    # hasn't been saved yet, so instance.id is always None. That's what was
    # producing "celebrants/None/<filename>" paths for every photo added at
    # creation time (only photos added later, via a separate update after
    # the id already existed, ever got a real numeric folder). A random
    # UUID exists before save and is unique regardless of when the file
    # is attached, so every upload gets a stable, collision-free path.
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
    return f'celebrants/{uuid.uuid4().hex}.{ext}'


class Celebrant(models.Model):
    MONTH_CHOICES = [(i, calendar.month_name[i]) for i in range(1, 13)]

    full_name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to=celebrant_photo_path, blank=True, null=True)
    birth_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    birth_day = models.PositiveSmallIntegerField()
    location = models.CharField(max_length=255, blank=True)
    big_wish = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='celebrants', null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    celebration_triggered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['birth_month', 'birth_day']

    def __str__(self):
        return self.full_name

    def clean(self):
        # Catch e.g. Feb 30, day 32, etc. Uses a leap year (2024) so Feb 29 is valid.
        days_in_month = calendar.monthrange(2024, self.birth_month)[1]
        if not (1 <= self.birth_day <= days_in_month):
            raise ValidationError({'birth_day': f'Invalid day for {calendar.month_name[self.birth_month]}.'})

    @property
    def is_birthday_today(self):
        today = timezone.localdate()
        return today.month == self.birth_month and today.day == self.birth_day

class Presence(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='presence')
    device_id = models.CharField(max_length=64, unique=True, db_index=True)
    last_seen = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-last_seen']
        verbose_name_plural = 'Presence'

    def __str__(self):
        who = self.user.username if self.user else 'guest'
        return f"{who} ({self.device_id[:8]}…) — last seen {self.last_seen}"


# ──────────────────────────────────────────────────────────────────────────────
# SiteCounter — simple key/value counters for site-wide numbers (e.g. total
# visits). One row per key, incremented atomically by the view.
# ──────────────────────────────────────────────────────────────────────────────

class SiteCounter(models.Model):
    key   = models.CharField(max_length=32, unique=True)
    value = models.BigIntegerField(default=0)

    def __str__(self):
        return f"{self.key} = {self.value}"