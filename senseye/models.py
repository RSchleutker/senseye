# -*- coding: utf-8 -*-
"""
Created on Mon Feb 25 16:45:11 2019

@author: Raphael
"""

import sys, os, struct
from ctypes import (CDLL,get_errno)
from ctypes.util import find_library
from socket import socket, AF_BLUETOOTH, SOCK_RAW, BTPROTO_HCI, SOL_HCI, HCI_FILTER, SHUT_RDWR

from datetime import datetime
from random import randint

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

from bluepy.btle import Scanner, DefaultDelegate


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
            return [Measurement(device = self.device,
                               sensor = self,
                               parameter = None,
                               time = datetime.now(),
                               value = None)]
        print("data",data[self.mac])
        battery = data[self.mac]['battery']
        temp = data[self.mac]['temp']
        humidity = data[self.mac]['humidity']

        measures = {'battery':(battery-70)/30*100,
                    'temperature':temp/10,
	            'humidity':humidity/10}
        print("measures_obj:", measures)
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

        scanner = Scanner().withDelegate(ScanDelegate([self.mac]))
        devices = scanner.scan(30.0, passive = True)
        measures = scanner.delegate.measures
        measurement = self.extract_data(measures)
        #print("measures",measurement)
        return measurement

class ScanDelegate(DefaultDelegate):
    def __init__(self, addresses):
        DefaultDelegate.__init__(self)
        self.addresses_to_scan = addresses 
        self.measures = {}

    def handleDiscovery(self, dev, isNewDev, isNewData):
        if (dev.addr in self.addresses_to_scan):
            for (atype, d, value) in dev.getScanData():
               if atype == 255:
                   self.measures[dev.addr] = {"battery":int(value[6:8],16),
                                         "temp":int(value[16:20],16),
                                          "humidity":int(value[20:24],16)}

class RaspberryPi(Base):
    """
    """
    __tablename__ = 'raspis'

    id = Column(Integer, primary_key = True)
    room = Column(String(32), nullable = False)
    ip = Column(String(64), nullable = False)
    port = Column(Integer, nullable = False)
