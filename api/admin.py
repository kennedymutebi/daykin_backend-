from django.contrib import admin
from .models import Celebrity, Article, Post, Charity, LoveStory


@admin.register(Celebrity)
class CelebrityAdmin(admin.ModelAdmin):
    list_display = ['name', 'profession', 'nationality', 'age', 'birth_date', 'is_birthday_today']
    search_fields = ['name', 'profession', 'nationality']
    list_filter = ['nationality']
    ordering = ['name']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'is_published', 'likes', 'reads', 'created_at']
    list_filter = ['category', 'is_published']
    search_fields = ['title', 'content']
    list_editable = ['is_published']
    autocomplete_fields = ['celebrity']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['user', 'content_preview', 'tag', 'likes', 'is_published', 'created_at']
    list_filter = ['tag', 'is_published']
    list_editable = ['is_published']
    search_fields = ['content', 'user__username']

    def content_preview(self, obj):
        return obj.content[:60]
    content_preview.short_description = 'Content'


@admin.register(Charity)
class CharityAdmin(admin.ModelAdmin):
    list_display  = ['title', 'tag', 'beneficiary', 'location', 'goal', 
                     'raised', 'donors', 'progress', 'urgent', 'is_active', 'created_at']
    list_filter   = ['tag', 'is_active', 'urgent']
    list_editable = ['is_active', 'urgent', 'raised', 'donors']
    search_fields = ['title', 'tag', 'beneficiary', 'location']

    def progress(self, obj):
        return f"{obj.progress}%"
    progress.short_description = 'Progress'


@admin.register(LoveStory)
class LoveStoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'likes', 'is_published', 'created_at']  # ← 'author' not 'author_name'
    list_filter = ['is_published']
    list_editable = ['is_published']
    search_fields = ['title', 'author__username', 'author__first_name', 'author__last_name']  # ← fix here too

    def author_display(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return '—'
    author_display.short_description = 'Author'