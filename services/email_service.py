# services/email_service.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_email(subject: str, body: str, to_email: str) -> None:
    from services.config_service import global_config
    cfg      = global_config.get()
    smtp_user = cfg.get("smtp_email", "").strip()
    smtp_pwd  = cfg.get("smtp_password", "").strip()

    if not smtp_user or not smtp_pwd:
        raise RuntimeError(
            "SMTP credentials are not configured.\n"
            "Go to Admin Settings → Email and set SMTP Email and Password."
        )

    template = cfg.get("email_template", "{company_name}\n\n{body}")
    content  = template.format(
        company_name=cfg.get("company_name", "SR Manager"), body=body)

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_email
    msg.attach(MIMEText(content, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.ehlo(); s.starttls(); s.login(smtp_user, smtp_pwd)
            s.sendmail(smtp_user, [to_email], msg.as_string())
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError("SMTP authentication failed. Check your Gmail App Password.")
    except Exception as e:
        raise RuntimeError(f"Email error: {e}")


def send_help_request(sender_name: str, sender_email: str, recipients: list) -> None:
    subject = f"Help Requested — {sender_name}"
    body    = (f"Technical user {sender_name} ({sender_email}) "
               f"has requested assistance from the SR Manager dashboard.\n\n"
               f"Please log in and review their assigned service requests.")
    errors = []
    for r in recipients:
        try:
            send_email(subject, body, r)
        except Exception as e:
            errors.append(str(e))
    if errors:
        raise RuntimeError("\n".join(errors))
