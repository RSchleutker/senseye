# -*- coding: utf-8 -*-
"""
Created on Tue Feb 26 08:43:13 2019

@author: Raphael
"""

from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class Mailer:

    def __init__(self, server, name, password, email_address, port = 587):
        self.server = server
        self.port = port
        self.name = name
        self.email_address = email_address
        self.password = password

    @property
    def password(self):
        return None

    @password.setter
    def password(self, password):
        self.__password = password

    def send_msg(self, recipients, subject, message):
        msg = MIMEMultipart()
        msg['From'] = self.email_address
        msg['To'] = ','.join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'plain'))

        with SMTP(self.server, self.port) as server:
            server.starttls()
            server.login(self.name, self.__password)
            server.sendmail(self.email_address,
                            recipients,
                            msg.as_string())
