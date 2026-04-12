"""
================================================================
  accounts/models.py — User Authentication Models
  Tables: USERS, LOGIN_HISTORY, OTPVerification
================================================================
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
import random


class CustomUserManager(BaseUserManager):
    """Manager for CustomUser — handles create_user and create_superuser."""

    def create_user(self, email, password=None, **extra_fields):
        """Create a regular user with email and password."""
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create a superuser (admin)."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Maps to: USERS table
    Uses email as login field instead of username.
    """
    ROLE_CHOICES   = [('patient', 'Patient'), ('admin', 'Admin')]
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]

    email         = models.EmailField(unique=True)
    name          = models.CharField(max_length=150)
    contact_no    = models.CharField(max_length=15, blank=True)
    role          = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    gender        = models.CharField(max_length=10, choices=GENDER_CHOICES, default='male')
    age           = models.PositiveIntegerField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    medical_notes = models.TextField(blank=True)
    profile_pic   = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    is_active     = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.name} ({self.email})"
    def save(self, *args, **kwargs):
        """
        Auto-calculate age from date_of_birth every time profile is saved.
        Age cannot exceed 100 years.
        """
        if self.date_of_birth:
            from datetime import date
            today = date.today()
            age   = today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
            # Cap age at 100
            self.age = min(age, 100)
        super().save(*args, **kwargs)


class LoginHistory(models.Model):
    """Maps to: LOGIN_HISTORY table — tracks every login."""
    user       = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_history')
    login_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'login_history'
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.name} — {self.login_time}"


class OTPVerification(models.Model):
    """Stores OTP codes for forgot password — expires in 5 minutes."""
    email      = models.EmailField()
    otp_code   = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    class Meta:
        db_table = 'otp_verification'

    def is_expired(self):
        """Returns True if OTP is older than 5 minutes."""
        from django.conf import settings
        expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expiry)

    @staticmethod
    def generate_otp():
        """Generate a random 6-digit OTP."""
        return str(random.randint(100000, 999999))

    def __str__(self):
        return f"OTP {self.otp_code} for {self.email}"
