"""
================================================================
  accounts/forms.py — All Authentication Forms
  Includes: Strong password, DOB validation, name/contact checks
================================================================
"""
import re
from datetime import date
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser


class LoginForm(AuthenticationForm):
    """Login form using email and password."""
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Email Address',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password',
        })
    )
    remember_me = forms.BooleanField(required=False)


class SignUpForm(forms.ModelForm):
    """Registration form with full validation."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password',
            'id': 'id_password',
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm Password',
        })
    )
    def clean_date_of_birth(self):
        """Validate DOB — no future date, max age 100."""
        from datetime import date
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = date.today()
            if dob > today:
                raise forms.ValidationError('Date of birth cannot be a future date.')
            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
            if age > 100:
                raise forms.ValidationError('Age cannot be more than 100 years.')
        return dob

    class Meta:
        model  = CustomUser
        fields = ['name', 'email', 'date_of_birth', 'contact_no']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Full Name',
                'pattern': '[A-Za-z ]+',
                'title': 'Name must contain only letters',
                'oninput': 'this.value=this.value.replace(/[^A-Za-z ]/g,"")',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Email Address',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
                'max': date.today().isoformat(),  # No future dates
            }),
            'contact_no': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contact Number (10 digits)',
                'maxlength': '10',
                'pattern': '[6-9][0-9]{9}',
                'inputmode': 'numeric',
                'title': 'Enter valid 10 digit Indian mobile number',
                'oninput': 'this.value=this.value.replace(/[^0-9]/g,"").slice(0,10)',
            }),
        }

    def clean_name(self):
        """Name must contain only letters and spaces."""
        name = self.cleaned_data.get('name', '').strip()
        if not all(c.isalpha() or c.isspace() for c in name):
            raise forms.ValidationError('Name must contain only letters and spaces.')
        if len(name) < 2:
            raise forms.ValidationError('Name must be at least 2 characters.')
        return name

    def clean_contact_no(self):
        """Contact must be exactly 10 digits starting with 6-9."""
        contact = self.cleaned_data.get('contact_no', '').strip()
        if contact:
            if not contact.isdigit():
                raise forms.ValidationError('Contact must contain only digits.')
            if len(contact) != 10:
                raise forms.ValidationError('Contact must be exactly 10 digits.')
            if contact[0] not in '6789':
                raise forms.ValidationError('Contact must start with 6, 7, 8, or 9.')
        return contact

    def clean_password(self):
        """
        Strong password validation:
        - Min 8 chars
        - At least 1 uppercase
        - At least 1 lowercase
        - At least 1 digit
        - At least 1 special character
        """
        password = self.cleaned_data.get('password')
        if password:
            if len(password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters.')
            if not re.search(r'[A-Z]', password):
                raise forms.ValidationError('Password must contain at least 1 uppercase letter.')
            if not re.search(r'[a-z]', password):
                raise forms.ValidationError('Password must contain at least 1 lowercase letter.')
            if not re.search(r'[0-9]', password):
                raise forms.ValidationError('Password must contain at least 1 number.')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise forms.ValidationError('Password must contain at least 1 special character.')
        return password

    def clean(self):
        """Validate both passwords match."""
        cleaned_data     = super().clean()
        password         = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data

    def save(self, commit=True):
        """Save user with hashed password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class ForgotPasswordEmailForm(forms.Form):
    """Step 1 of OTP reset — email input."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Registered Email',
        })
    )


class OTPVerifyForm(forms.Form):
    """Step 2 of OTP reset — 6 digit OTP input."""
    otp = forms.CharField(
        max_length=6, min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-input otp-input',
            'placeholder': '• • • • • •',
            'maxlength': '6',
            'inputmode': 'numeric',
        })
    )


class SetNewPasswordForm(forms.Form):
    """Step 3 of OTP reset — new password with strength validation."""
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New Password',
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm New Password',
        })
    )

    def clean_new_password(self):
        """Strong password validation."""
        password = self.cleaned_data.get('new_password')
        if password:
            if len(password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters.')
            if not re.search(r'[A-Z]', password):
                raise forms.ValidationError('Must contain at least 1 uppercase letter.')
            if not re.search(r'[a-z]', password):
                raise forms.ValidationError('Must contain at least 1 lowercase letter.')
            if not re.search(r'[0-9]', password):
                raise forms.ValidationError('Must contain at least 1 number.')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise forms.ValidationError('Must contain at least 1 special character.')
        return password

    def clean(self):
        cleaned_data     = super().clean()
        new_password     = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    """Profile update form with all validations."""
    class Meta:
        model  = CustomUser
        fields = ['name', 'email', 'age', 'gender', 'contact_no', 'medical_notes', 'profile_pic']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Full Name',
                'oninput': 'this.value=this.value.replace(/[^A-Za-z ]/g,"")',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'readonly': 'readonly',
            }),
            'age': forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Auto-calculated from DOB',
            'readonly': 'readonly',  # ← User cannot manually type age
            }),
            'gender': forms.Select(attrs={'class': 'form-input'}),
            'contact_no': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contact Number',
                'maxlength': '10',
                'inputmode': 'numeric',
                'oninput': 'this.value=this.value.replace(/[^0-9]/g,"").slice(0,10)',
            }),
            'medical_notes': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Any allergies or past illness...',
                'rows': 4,
            }),
            'profile_pic': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*',
            }),
        }

    def clean_date_of_birth(self):
        """
        Validate DOB:
        - Cannot be future date
        - Person cannot be more than 100 years old
        """
        from datetime import date
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = date.today()
            # No future dates
            if dob > today:
                raise forms.ValidationError('Date of birth cannot be a future date.')
            # Calculate age
            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
            # Max age 100
            if age > 100:
                raise forms.ValidationError('Age cannot be more than 100 years.')
            if age < 0:
                raise forms.ValidationError('Invalid date of birth.')
        return dob

    def clean_age(self):
        """Age must be between 1 and 100 only."""
        age = self.cleaned_data.get('age')
        if age is not None:
            if age < 1 or age > 100:
                raise forms.ValidationError('Age must be between 1 and 100.')
        return age

    def clean_contact_no(self):
        """Contact must be 10 digits starting with 6-9."""
        contact = self.cleaned_data.get('contact_no', '').strip()
        if contact:
            if not contact.isdigit() or len(contact) != 10:
                raise forms.ValidationError('Enter valid 10 digit contact number.')
            if contact[0] not in '6789':
                raise forms.ValidationError('Contact must start with 6, 7, 8, or 9.')
        return contact
