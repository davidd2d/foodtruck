# apps/accounts/urls.py
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from .views import confirm_email, register, signup, logout_view, profile, profile_redirect
from accounts.forms import CustomAuthenticationForm

app_name = "accounts"

urlpatterns = [
    path("logout/", logout_view, name="logout"),
    path("login/", auth_views.LoginView.as_view(
        template_name="registration/login.html",
        authentication_form=CustomAuthenticationForm, 
        ), name="login"),
    path("signup/", signup, name="signup"),
    path('confirm-email/<str:token>/', confirm_email, name='confirm_email'),
    path("register/", register, name="register"),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset_form.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done')
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html'
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('profile/', profile_redirect, name='profile-redirect'),
    path('foodtruck/<slug:slug>/profile/', profile, name='profile'),
]
