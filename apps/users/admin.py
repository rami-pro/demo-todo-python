from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    """
    StackedInline renders each field on its own row within the User detail page.
    TabularInline would render them as a compact table row instead.
    can_delete=False prevents admins from removing the profile via this form.
    """

    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ["preferences"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Extends Django's built-in UserAdmin to add our custom fields.

    list_display    → columns shown on the changelist page
    list_filter     → sidebar filter checkboxes
    search_fields   → fields used when typing in the search bar (LIKE queries)
    readonly_fields → shown in the detail form but not editable
    inlines         → related models rendered on the same page
    fieldsets       → groups fields into sections on the detail page
    """

    inlines = [UserProfileInline]
    list_display = ["username", "email", "bio", "is_active", "is_staff", "created_at"]
    list_filter = ["is_active", "is_staff", "created_at"]
    search_fields = ["username", "email", "bio"]
    readonly_fields = ["id", "created_at"]

    fieldsets = BaseUserAdmin.fieldsets + (  # type: ignore[operator]
        ("Extended Profile", {"fields": ("bio", "avatar_url", "created_at")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Extended Profile", {"fields": ("email", "bio")}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["user", "updated_at"]
    readonly_fields = ["updated_at"]
    search_fields = ["user__username", "user__email"]
