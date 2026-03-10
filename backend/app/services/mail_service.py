import smtplib
from email.mime.text import MIMEText

from app.config import Config


class MailService:
    """简单邮件服务；未配置 SMTP 时回退为开发模式。"""

    def is_configured(self):
        return bool(Config.SMTP_HOST and Config.SMTP_FROM)

    def send_verification_code(self, email, code):
        subject = 'KnowledgeRec 邮箱验证码'
        body = (
            f'你的验证码是：{code}\n\n'
            '验证码 10 分钟内有效，请勿泄露给他人。'
        )
        return self.send_text_email(email, subject, body)

    def send_text_email(self, email, subject, body):
        """发送纯文本邮件"""
        if not self.is_configured():
            print(f'[MailService] DEV email={email} subject={subject}\n{body}')
            return {'mode': 'dev'}

        message = MIMEText(body, 'plain', 'utf-8')
        message['Subject'] = subject
        message['From'] = Config.SMTP_FROM
        message['To'] = email

        if Config.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                self._login_if_needed(server)
                server.sendmail(Config.SMTP_FROM, [email], message.as_string())
        else:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                if Config.SMTP_USE_TLS:
                    server.starttls()
                self._login_if_needed(server)
                server.sendmail(Config.SMTP_FROM, [email], message.as_string())

        return {'mode': 'smtp'}

    def get_status(self):
        return {
            'configured': self.is_configured(),
            'host': Config.SMTP_HOST,
            'port': Config.SMTP_PORT,
            'from': Config.SMTP_FROM,
            'use_ssl': Config.SMTP_USE_SSL,
            'use_tls': Config.SMTP_USE_TLS,
            'mode': 'smtp' if self.is_configured() else 'dev',
        }

    def _login_if_needed(self, server):
        if Config.SMTP_USER and Config.SMTP_PASSWORD:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)


mail_service = MailService()
