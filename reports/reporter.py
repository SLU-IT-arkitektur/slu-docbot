import time
import smtplib
import os
from weasyprint import HTML
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from generate_report import generate_report
from datetime import datetime

generate_report()

# get chatbot url from env var
chatbot_url = os.getenv('CHATBOT_URL')
if chatbot_url is None:
    print("CHATBOT_URL env var not set")
    exit(1)

# get receivers as a comma separated string from env var
receivers = os.getenv('REPORT_RECEIVERS')
if receivers is None:
    print("REPORT_RECEIVERS env var not set")
    exit(1)

receivers = receivers.split(',')
if len(receivers) == 0:
    print("No receivers found")
    exit(1)

# get password from env var
password = os.getenv('REPORT_SENDER_PASSWORD')
if password is None:
    print("REPORT_SENDER_PASSWORD env var not set")
    exit(1)


# get smtp host from env var
smtp_host = os.getenv('REPORT_SMTP_HOST')
if smtp_host is None:
    print("REPORT_SMTP_HOST env var not set")
    exit(1)

# get smtp port from env var
smtp_port = os.getenv('REPORT_SMTP_PORT')
if smtp_port is None:
    print("REPORT_SMTP_PORT env var not set")
    exit(1)

today = datetime.now().strftime('%Y-%m-%d')
subject = f'Report for {chatbot_url} {today}'
body = f'Se rapporten för {chatbot_url} {today} i bifogad pdf.'

sender = "noreply@app.slu.se"

HTML(filename='report.html').write_pdf('report.pdf')
print('saved ./report.pdf')


def send_email(subject, body, sender, recipients, password):
    msg = MIMEMultipart()
    body_part = MIMEText(body)
    msg.attach(body_part)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    with open('report.pdf', 'rb') as file:
        part = MIMEApplication(file.read(), Name="report.pdf")
        part['Content-Disposition'] = 'attachment; filename="report.pdf"'
        msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port) as smtp_server:

            # smtp_server.login(sender, password)
            smtp_server.sendmail(from_addr=sender, to_addrs=receivers, msg=msg.as_string())
    print("Message sent!")


def try_connect_to_smtp(retries=10, delay_in_seconds=5):
    for i in range(retries):
        try:
            with smtplib.SMTP(smtp_host, smtp_port):
                print("Connected to smtp server")
                return
        except Exception as e:
            attempt = i + 1
            if attempt >= retries:
                print(f'failed with {e}')
                raise
            else:
                print(f'failed to connect to smtp with error {e}, will retry (attempt {attempt}/{retries}) in {delay_in_seconds} seconds')
                print('sleeping 5 seconds before trying again..')
                time.sleep(5)
                continue


try_connect_to_smtp()
send_email(subject, body, sender, receivers, password)
