"""
================================================================
  accounts/views.py — Authentication Views
  Handles: Login, Signup, OTP Password Reset, Profile
================================================================
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from .models import CustomUser, LoginHistory, OTPVerification
from .forms import (
    LoginForm, SignUpForm, ForgotPasswordEmailForm,
    OTPVerifyForm, SetNewPasswordForm, ProfileUpdateForm
)


def login_view(request):
    """
    Handles user login.
    GET  → Show login form
    POST → Authenticate and redirect to dashboard
    Records login in LOGIN_HISTORY table.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user        = form.get_user()
            remember_me = form.cleaned_data.get('remember_me')
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            # Record login history
            LoginHistory.objects.create(
                user=user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f'Welcome back, {user.name}! 👋')
            return redirect(request.GET.get('next', 'dashboard'))
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def signup_view(request):
    """
    Handles new user registration.
    GET  → Show signup form
    POST → Validate, create user, login, redirect
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.name}! Account created! 🎉')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


def logout_view(request):
    """Logs out user and redirects to login."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


def forgot_password_view(request):
    """
    Step 1: User enters registered email.
    Generates OTP, saves to DB, sends to email.
    """
    if request.method == 'POST':
        form = ForgotPasswordEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            if not CustomUser.objects.filter(email=email).exists():
                messages.error(request, 'No account found with this email.')
                return render(request, 'accounts/forgot_password.html', {'form': form})

            # Delete old OTPs for this email
            OTPVerification.objects.filter(email=email, is_used=False).delete()

            # Generate and save new OTP
            otp_code = OTPVerification.generate_otp()
            OTPVerification.objects.create(email=email, otp_code=otp_code)

            # Send OTP to email
            try:
                send_mail(
                    subject='Smart Disease Prediction — Password Reset OTP',
                    message=f'''Hello,

Your OTP for password reset is: {otp_code}

This OTP is valid for 5 minutes only.
Do not share this OTP with anyone.

Regards,
Smart Disease Prediction Team''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
            except Exception:
                # In development prints to console
                print(f"[OTP] {email}: {otp_code}")

            request.session['reset_email'] = email
            messages.success(request, f'OTP sent to {email}!')
            return redirect('verify_otp')
    else:
        form = ForgotPasswordEmailForm()

    return render(request, 'accounts/forgot_password.html', {'form': form})


def verify_otp_view(request):
    """
    Step 2: User enters 6-digit OTP.
    Validates code, expiry, and marks as used.
    """
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == 'POST':
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']
            try:
                otp_obj = OTPVerification.objects.filter(
                    email=email, otp_code=entered_otp, is_used=False
                ).latest('created_at')

                if otp_obj.is_expired():
                    messages.error(request, 'OTP has expired. Please request a new one.')
                    return render(request, 'accounts/verify_otp.html', {'form': form, 'email': email})

                otp_obj.is_used = True
                otp_obj.save()
                request.session['otp_verified'] = True
                return redirect('set_new_password')

            except OTPVerification.DoesNotExist:
                messages.error(request, 'Invalid OTP. Please try again.')
    else:
        form = OTPVerifyForm()

    return render(request, 'accounts/verify_otp.html', {'form': form, 'email': email})


def resend_otp_view(request):
    """Resends a fresh OTP to the user's email."""
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    OTPVerification.objects.filter(email=email, is_used=False).delete()
    otp_code = OTPVerification.generate_otp()
    OTPVerification.objects.create(email=email, otp_code=otp_code)

    try:
        send_mail(
            subject='Smart Disease — New OTP',
            message=f'Your new OTP is: {otp_code}\nValid for 5 minutes.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
    except Exception:
        print(f"[OTP] {email}: {otp_code}")

    messages.success(request, 'New OTP sent!')
    return redirect('verify_otp')


def set_new_password_view(request):
    """Step 3: User sets new password after OTP verified."""
    if not request.session.get('otp_verified'):
        return redirect('forgot_password')

    email = request.session.get('reset_email')

    if request.method == 'POST':
        form = SetNewPasswordForm(request.POST)
        if form.is_valid():
            user = CustomUser.objects.get(email=email)
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            del request.session['reset_email']
            del request.session['otp_verified']
            messages.success(request, 'Password reset successfully! Please login.')
            return redirect('login')
    else:
        form = SetNewPasswordForm()

    return render(request, 'accounts/set_new_password.html', {'form': form})


@login_required
def profile_view(request):
    """Shows user profile page."""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def update_profile_view(request):
    """
    Handles profile update.
    GET  → Pre-fill form with current data
    POST → Save updated profile
    """
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully! ✅')
            return redirect('profile')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'accounts/update_profile.html', {'form': form})
