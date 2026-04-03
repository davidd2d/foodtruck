# apps/accounts/utils.py
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext as _

signer = TimestampSigner()

def generate_email_confirmation_token(user):
    return signer.sign(user.pk)

def verify_email_confirmation_token(token, max_age=60*60*24):  # 24 heures
    try:
        user_pk = signer.unsign(token, max_age=max_age)
        return int(user_pk)
    except (BadSignature, SignatureExpired):
        return None

def send_confirmation_email(user, request):
    token = generate_email_confirmation_token(user)
    confirmation_link = request.build_absolute_uri(
        reverse("accounts:confirm_email", args=[token])
    )
    context = {"user": user, "confirmation_link": confirmation_link}
    subject = _("Confirmation de votre adresse e-mail")
    body = render_to_string("accounts/email_confirmation.html", context)
    send_mail(subject, "", settings.DEFAULT_FROM_EMAIL, [user.email], html_message=body)