from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, LoginHistory, OTPVerification

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'name', 'role', 'contact_no', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'gender')
    search_fields = ('email', 'name')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('name', 'gender', 'age', 'date_of_birth', 'contact_no', 'medical_notes', 'profile_pic')}),
        ('Role', {'fields': ('role',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'name', 'password1', 'password2', 'role')}),
    )

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'login_time', 'ip_address')

@admin.register(OTPVerification)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'otp_code', 'created_at', 'is_used')
