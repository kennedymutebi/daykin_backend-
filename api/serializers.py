from rest_framework import serializers
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_field
from .models import Presence, SiteCounter


from .models import Celebrant


from rest_framework import serializers


from .models import (
    Celebrity, Article, Post, Charity,
    LoveStory, LoveStoryComment,
    Subscription,
)


# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model  = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


# ──────────────────────────────────────────────────────────────────────────────
# Celebrity
# ──────────────────────────────────────────────────────────────────────────────

class CelebritySerializer(serializers.ModelSerializer):
    age               = serializers.SerializerMethodField()
    is_birthday_today = serializers.SerializerMethodField()

    class Meta:
        model  = Celebrity
        fields = '__all__'

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_age(self, obj) -> int | None:
        return obj.age

    @extend_schema_field(serializers.BooleanField())
    def get_is_birthday_today(self, obj) -> bool:
        return obj.is_birthday_today


# ──────────────────────────────────────────────────────────────────────────────
# Shared author info (reused by Article + LoveStory)
# ──────────────────────────────────────────────────────────────────────────────

class AuthorInfoSerializer(serializers.Serializer):
    name          = serializers.CharField()
    avatar        = serializers.CharField()
    verified      = serializers.BooleanField()
    gradient_from = serializers.CharField()
    gradient_to   = serializers.CharField()
    is_subscribed = serializers.BooleanField()


def _build_author_info(author: User, request) -> dict:
    name = author.get_full_name() or author.username
    is_subscribed = False
    if request and request.user.is_authenticated:
        is_subscribed = Subscription.objects.filter(
            subscriber=request.user, author=author
        ).exists()
    return {
        'name':          name,
        'avatar':        name[:2].upper(),
        'verified':      author.is_staff,
        'gradient_from': '#F5A623',
        'gradient_to':   '#E91E8C',
        'is_subscribed': is_subscribed,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Article
# ──────────────────────────────────────────────────────────────────────────────

class ArticleSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_info = serializers.SerializerMethodField()
    read_time   = serializers.SerializerMethodField()

    class Meta:
        model  = Article
        fields = '__all__'
        read_only_fields = [
            'author', 'created_at', 'updated_at',
            'likes', 'comments', 'shares', 'reads',
        ]

    @extend_schema_field(serializers.CharField())
    def get_author_name(self, obj) -> str:
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return 'Admin'

    @extend_schema_field(AuthorInfoSerializer)
    def get_author_info(self, obj):
        if not obj.author:
            return None
        return _build_author_info(obj.author, self.context.get('request'))

    @extend_schema_field(serializers.CharField())
    def get_read_time(self, obj) -> str:
        return obj.read_time


# ──────────────────────────────────────────────────────────────────────────────
# Post
# ──────────────────────────────────────────────────────────────────────────────

class PostUserInfoSerializer(serializers.Serializer):
    name     = serializers.CharField()
    handle   = serializers.CharField()
    avatar   = serializers.CharField()
    verified = serializers.BooleanField()


class PostSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()

    class Meta:
        model  = Post
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'likes', 'comments', 'shares']

    @extend_schema_field(PostUserInfoSerializer)
    def get_user_info(self, obj) -> dict:
        name = obj.user.get_full_name() or obj.user.username
        return {
            'name':     name,
            'handle':   obj.user.username,
            'avatar':   name[:2].upper(),
            'verified': obj.user.is_staff,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Charity
# ──────────────────────────────────────────────────────────────────────────────

class CharitySerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()

    class Meta:
        model  = Charity
        fields = '__all__'
        read_only_fields = ['created_at']

    @extend_schema_field(serializers.IntegerField())
    def get_progress(self, obj) -> int:
        return obj.progress


# ──────────────────────────────────────────────────────────────────────────────
# Love Story Comment
# ──────────────────────────────────────────────────────────────────────────────

class LoveStoryCommentSerializer(serializers.ModelSerializer):
    author   = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    class Meta:
        model  = LoveStoryComment
        fields = ['id', 'author', 'initials', 'text', 'created_at']
        read_only_fields = ['id', 'author', 'initials', 'created_at']

    @extend_schema_field(serializers.CharField())
    def get_author(self, obj) -> str:
        return obj.user.get_full_name() or obj.user.username

    @extend_schema_field(serializers.CharField())
    def get_initials(self, obj) -> str:
        name = obj.user.get_full_name() or obj.user.username
        return name[:2].upper()


# ──────────────────────────────────────────────────────────────────────────────
# Love Story
# ──────────────────────────────────────────────────────────────────────────────

class LoveStorySerializer(serializers.ModelSerializer):
    author_info = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    read_time   = serializers.SerializerMethodField()
    # Whether the requesting user has already liked this story
    liked       = serializers.SerializerMethodField()

    class Meta:
        model  = LoveStory
        fields = '__all__'
        read_only_fields = [
            'author', 'is_published',
            'created_at', 'likes', 'comments', 'shares',
        ]

    @extend_schema_field(AuthorInfoSerializer)
    def get_author_info(self, obj):
        if not obj.author:
            return None
        return _build_author_info(obj.author, self.context.get('request'))

    @extend_schema_field(serializers.CharField())
    def get_author_name(self, obj) -> str:
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return 'Anonymous'

    @extend_schema_field(serializers.CharField())
    def get_read_time(self, obj) -> str:
        return obj.read_time

    @extend_schema_field(serializers.BooleanField())
    def get_liked(self, obj) -> bool:
        """True if the current authenticated user has already liked this story."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.story_likes.filter(user=request.user).exists()


# ──────────────────────────────────────────────────────────────────────────────
# Subscription
# ──────────────────────────────────────────────────────────────────────────────

class SubscriptionSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model  = Subscription
        fields = ['id', 'author', 'author_name', 'created_at']
        read_only_fields = ['subscriber', 'created_at']

    @extend_schema_field(serializers.CharField())
    def get_author_name(self, obj) -> str:
        return obj.author.get_full_name() or obj.author.username




class CelebrantSerializer(serializers.ModelSerializer):
    is_birthday_today = serializers.BooleanField(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Celebrant
        fields = [
            'id', 'full_name', 'photo', 'birth_month', 'birth_day',
            'location', 'big_wish', 'created_at', 'is_birthday_today',
            'created_by', 'is_owner',
        ]
        read_only_fields = ['created_at', 'created_by']

    def get_is_owner(self, obj) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.created_by_id == request.user.id

    def validate(self, data):
        instance = Celebrant(**{k: v for k, v in data.items() if k != 'photo'})
        instance.clean()
        return data

    def create(self, validated_data):
        return Celebrant.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class OnlineUserSerializer(serializers.ModelSerializer):
    name     = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'name', 'initials']

    @extend_schema_field(serializers.CharField())
    def get_name(self, obj) -> str:
        return obj.get_full_name() or obj.username

    @extend_schema_field(serializers.CharField())
    def get_initials(self, obj) -> str:
        name = obj.get_full_name() or obj.username
        return name[:2].upper()


# ──────────────────────────────────────────────────────────────────────────────
# Presence ping — request/response shapes for POST /api/presence/ping/
# ──────────────────────────────────────────────────────────────────────────────

class PresencePingSerializer(serializers.Serializer):
    """Validates the incoming { "device_id": "<uuid>" } body."""
    device_id = serializers.CharField(max_length=64)


class PresencePingResponseSerializer(serializers.Serializer):
    online_now = serializers.IntegerField()


# ──────────────────────────────────────────────────────────────────────────────
# Online presence — response shape for GET /api/presence/online/
# ──────────────────────────────────────────────────────────────────────────────

class OnlinePresenceSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    users = OnlineUserSerializer(many=True)


# ──────────────────────────────────────────────────────────────────────────────
# Site stats — response shape for GET /api/stats/
# ──────────────────────────────────────────────────────────────────────────────

class SiteStatsSerializer(serializers.Serializer):
    members           = serializers.IntegerField()
    stories_published = serializers.IntegerField()
    total_visits      = serializers.IntegerField()
    online_now        = serializers.IntegerField()