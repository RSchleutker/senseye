# -*- coding: utf-8 -*-
"""
Created on Mon Feb 25 16:45:11 2019

@author: Raphael
"""

import sys, os, struct
from ctypes import (CDLL,get_errno)
from ctypes.util import find_library
#from socket import socket, AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI, SOL_HCI, HCI_FILTER, SHUT_RDWR

from datetime import datetime
from random import randint

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash


Base = declarative_base()

class User(Base):
    """
    """
    __tablename__ = 'user'

    username = Column(String(64), primary_key = True)
    email = Column(String(64), nullable = False)
    password_hash = Column(String(256), nullable = False)
    group = Column(String(32), nullable = False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Range(Base):
    """A Range class to store allowed ranges for a device.

    :param parameter: a string of the parameter, e.g. `temperature` or
                      `humidity`.
    :param lower: a numeric value that represents the lower limit.
    :param upper: a numeric value that represents the upper limit.
    """
    __tablename__ = 'ranges'

    device = Column(Integer, ForeignKey('devices.id'), primary_key = True)
    parameter = Column(String(32), primary_key = True)
    lower = Column(Float, nullable = False)
    upper = Column(Float, nullable = False)

class Device(Base):
    """A Device class.
    """
    __tablename__ = 'devices'

    id = Column(Integer, primary_key = True)
    type = Column(String(32), nullable = False)
    room = Column(String(32))
    group = Column(String(32))

class Measurement(Base):
    """
    """
    __tablename__ = 'measurements'

    device = Column(Integer, ForeignKey('devices.id'), primary_key = True)
    sensor = Column(Integer, ForeignKey('sensors.id'), primary_key = True)
    parameter = Column(String(32), primary_key = True)
    time = Column(DateTime, primary_key = True)
    value = Column(Float)

class Sensor(Base):
    """A sensor class for bluemaestro sensors.

    :param ident: identification integer (id) of the sensor.
    :param mac: MAC address of the sensor as string.
    :param device: identification integer (id) of the device the sensor is
                   attached to.
    :param raspi:
    """
    __tablename__ = 'sensors'

    id = Column(Integer, primary_key = True)
    mac = Column(String(32), nullable = False)
    device = Column(Integer, ForeignKey('devices.id'))
    raspi = Column(Integer, ForeignKey('raspis.id'))

    def extract_data(self, data):
        """Extract the last measurements from the requested data and returns a
        Measurement object.

        :param data: raw byte data as read from the sensor.

        :return: Measurement.
        """
        if not data:
            return Measurement(device = self.device,
                               sensor = self,
                               parameter = None,
                               time = datetime.now(),
                               value = None)

        battery = int.from_bytes(data[22:23], byteorder = 'little')
        temp = int.from_bytes(data[28:26:-1], byteorder = 'little', signed = True)
        humidity = int.from_bytes(data[30:28:-1], byteorder = 'little')

        measures = {'battery':(battery-70)/30*100,
                    'temperature':temp/10,
                    'humidity':humidity/10}

        # Return a list of measurements.
        return [Measurement(device = self.device,
                            sensor = self.id,
                            parameter = param,
                            time = datetime.now(),
                            value = val) for (param, val) in measures.items()]

    def measure_mockup(self):
        """A mockup function to simulate measuring without a real bluetooth
        sensor.

        :return: Measurement.
        """

        PARAMS = ['temperature', 'humidity', 'battery']

        return [Measurement(device = self.device,
                           sensor = self.id,
                           parameter = param,
                           time = datetime.now(),
                           value = randint(0,75)) for param in PARAMS]

    def measure(self):
        """Measures the data from the physical sensor.

        :return: Measurement. The measurement object is obtained by sending the
                 raw byte data to the `Sensor.extract_data()` static method.
        """

        if not os.geteuid() == 0:
            raise RuntimeError("Must be called as root!")

        btlib = find_library("bluetooth")
        if not btlib:
            raise ImportError("Can't find library: bluetooth")

        bluez = CDLL(btlib, use_errno = True)

        dev_id = bluez.hci_get_route(None)

        sock = socket(AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI)
        sock.bind((dev_id,))

        err = bluez.hci_le_set_scan_parameters(sock.fileno(),
                                               0, 0x10, 0x10, 0, 0, 1000);

        if err < 0:
            #sock.shutdown(SHUT_RDWR)
            sock.close()
            raise Exception("Set scan parameters failed")
            # occurs when scanning is still enabled from previous call

        # allows LE advertising events
        hci_filter = struct.pack(
                "<IQH",
                0x00000010,
                0x4000000000000000,
                0
                )
        sock.setsockopt(SOL_HCI, HCI_FILTER, hci_filter)

        err = bluez.hci_le_set_scan_enable(
                sock.fileno(),
                1,  # 1 - turn on;  0 - turn off
                0, # 0-filtering disabled, 1-filter out duplicates
                1000  # timeout
                )

        if err < 0:
            errnum = get_errno()
            raise Exception("{} {}".format(
                    errno.errorcode[errnum],
                    os.strerror(errnum)
                    ))
        tries = 0

        while True:
            data = sock.recv(1024)
            # print bluetooth address from LE Advert. packet
            mac = ':'.join("{0:02x}".format(x) for x in data[12:6:-1])
            #Address from advert packet is id, then read and stop
            if mac == self.mac:
                measurements = Sensor.extract_data(data)
                break
            #Prevent while to run forever.
            if tries > 20:
                measurements = Sensor.extract_data(None)
                break
            tries += 1

        err = bluez.hci_le_set_scan_enable(
                sock.fileno(),
                0,  # 1 - turn on;  0 - turn off
                0, # 0-filtering disabled, 1-filter out duplicates
                1000  # timeout
                )

        #sock.shutdown(SHUT_RDWR)
        sock.close()

        return measurements

class RaspberryPi(Base):
    """
    """
    __tablename__ = 'raspis'

    id = Column(Integer, primary_key = True)
    room = Column(String(32), nullable = False)
    ip = Column(String(64), nullable = False)
    port = Column(Integer, nullable = False)