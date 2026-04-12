from django.urls import path
from . import views

urlpatterns = [
    path('login/',           views.login_view,           name='login'),
    path('signup/',          views.signup_view,          name='signup'),
    path('logout/',          views.logout_view,          name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('verify-otp/',      views.verify_otp_view,      name='verify_otp'),
    path('resend-otp/',      views.resend_otp_view,      name='resend_otp'),
    path('set-new-password/',views.set_new_password_view,name='set_new_password'),
    path('profile/',         views.profile_view,         name='profile'),
    path('profile/update/',  views.update_profile_view,  name='update_profile'),
]
