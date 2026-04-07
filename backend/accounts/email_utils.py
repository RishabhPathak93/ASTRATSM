import json
import logging
from html import escape
from urllib import parse, request
from urllib.error import HTTPError

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail

logger = logging.getLogger('nexus')


class OTPEmailError(Exception):
    pass


class NotificationEmailError(Exception):
    pass


BRAND_PRIMARY = '#1d4ed8'
BRAND_DARK = '#0f172a'
BRAND_MUTED = '#475569'
SURFACE = '#f8fafc'
CARD = '#ffffff'
BORDER = '#e2e8f0'


def format_duration_seconds(seconds: int) -> str:
    seconds = max(int(seconds or 0), 0)
    minutes, remaining = divmod(seconds, 60)
    parts = []
    if minutes:
        parts.append(f'{minutes} minute' + ('s' if minutes != 1 else ''))
    if remaining:
        parts.append(f'{remaining} second' + ('s' if remaining != 1 else ''))
    return ' '.join(parts) or '0 seconds'


def _graph_access_token():
    payload = parse.urlencode({
        'client_id': settings.MS_GRAPH_CLIENT_ID,
        'client_secret': settings.MS_GRAPH_CLIENT_SECRET,
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials',
    }).encode('utf-8')
    token_url = f'https://login.microsoftonline.com/{settings.MS_GRAPH_TENANT_ID}/oauth2/v2.0/token'
    req = request.Request(token_url, data=payload, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with request.urlopen(req, timeout=15) as response:
        body = json.loads(response.read().decode('utf-8'))
    return body['access_token']


def _send_via_graph(recipients, subject: str, body: str, content_type: str = 'Text'):
    token = _graph_access_token()
    sender = settings.MS_GRAPH_SENDER_EMAIL
    endpoint = f'https://graph.microsoft.com/v1.0/users/{parse.quote(sender)}/sendMail'
    payload = {
        'message': {
            'subject': subject,
            'body': {'contentType': content_type, 'content': body},
            'toRecipients': [{'emailAddress': {'address': email}} for email in recipients],
        },
        'saveToSentItems': True,
    }
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with request.urlopen(req, timeout=15):
        return None


def _send_email(recipients, subject: str, plain_body: str, html_body: str | None = None):
    recipients = [email.strip().lower() for email in recipients if email]
    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        return

    if all([
        settings.MS_GRAPH_TENANT_ID,
        settings.MS_GRAPH_CLIENT_ID,
        settings.MS_GRAPH_CLIENT_SECRET,
        settings.MS_GRAPH_SENDER_EMAIL,
    ]):
        _send_via_graph(recipients, subject, html_body or plain_body, 'HTML' if html_body else 'Text')
        return

    if html_body:
        message = EmailMultiAlternatives(subject, plain_body, settings.DEFAULT_FROM_EMAIL, recipients)
        message.attach_alternative(html_body, 'text/html')
        message.send(fail_silently=False)
        return

    send_mail(subject, plain_body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)


def build_no_reply_email(subject: str, heading: str, intro: str, details=None, footer_note: str | None = None):
    details = details or []
    escaped_subject = escape(subject)
    escaped_heading = escape(heading)
    escaped_intro = escape(intro)
    rows_html = ''.join(
        f"<tr><td style='padding:8px 0;color:{BRAND_MUTED};font-size:13px;font-weight:600;width:160px'>{escape(str(label))}</td><td style='padding:8px 0;color:{BRAND_DARK};font-size:13px'>{escape(str(value))}</td></tr>"
        for label, value in details
    )
    footer_note = footer_note or 'This is an automated message from AstraTSM. Please do not reply to this email.'
    html_body = f"""
    <div style="margin:0;padding:24px;background:{SURFACE};font-family:Segoe UI,Arial,sans-serif;color:{BRAND_DARK}">
      <div style="max-width:680px;margin:0 auto;background:{CARD};border:1px solid {BORDER};border-radius:18px;overflow:hidden">
        <div style="padding:20px 28px;background:{BRAND_DARK};color:#ffffff">
          <div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;opacity:.8">AstraTSM Notification</div>
          <div style="font-size:24px;font-weight:700;margin-top:8px">{escaped_subject}</div>
        </div>
        <div style="padding:28px">
          <div style="font-size:20px;font-weight:700;margin-bottom:10px">{escaped_heading}</div>
          <div style="font-size:14px;line-height:1.7;color:{BRAND_MUTED};margin-bottom:18px">{escaped_intro}</div>
          <div style="background:{SURFACE};border:1px solid {BORDER};border-radius:14px;padding:18px 20px;margin-bottom:18px">
            <table style="width:100%;border-collapse:collapse">{rows_html}</table>
          </div>
          <div style="font-size:12px;line-height:1.7;color:{BRAND_MUTED};padding-top:12px;border-top:1px solid {BORDER}">{escape(footer_note)}</div>
        </div>
      </div>
    </div>
    """.strip()

    plain_lines = [subject, '', heading, '', intro, '']
    for label, value in details:
        plain_lines.append(f'{label}: {value}')
    plain_lines.extend(['', footer_note])
    plain_body = '\n'.join(plain_lines)
    return plain_body, html_body


def send_otp_email(to_email: str, otp: str, user_name: str = ''):
    subject = 'Your AstraTSM login OTP'
    plain_body, html_body = build_no_reply_email(
        subject=subject,
        heading=f'Hello {user_name or to_email},',
        intro='Use the one-time passcode below to complete your sign in. This OTP can be used only once.',
        details=[
            ('One-time code', otp),
            ('Expires in', format_duration_seconds(settings.LOGIN_OTP_TTL_SECONDS)),
        ],
        footer_note='If you did not try to sign in, please ignore this email and contact your administrator. This mailbox is not monitored.',
    )

    try:
        _send_email([to_email], subject, plain_body, html_body)
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        logger.exception('Failed to send OTP email via Microsoft Graph: %s', detail)
        raise OTPEmailError('Could not send OTP email.') from exc
    except Exception as exc:
        logger.exception('Failed to send OTP email')
        raise OTPEmailError('Could not send OTP email.') from exc


def send_notification_email(recipients, subject: str, plain_body: str, html_body: str | None = None):
    try:
        _send_email(recipients, subject, plain_body, html_body)
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        logger.exception('Failed to send notification email via Microsoft Graph: %s', detail)
        raise NotificationEmailError('Could not send notification email.') from exc
    except Exception as exc:
        logger.exception('Failed to send notification email')
        raise NotificationEmailError('Could not send notification email.') from exc
