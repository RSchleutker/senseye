# -*- coding: utf-8 -*-
"""
Created on Tue Feb 26 09:08:42 2019

@author: Raphael
"""

from .models import *
from .mailer import Mailer

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import and_, or_, desc
from sqlalchemy.orm import sessionmaker, scoped_session

import socket
import pickle
from threading import Thread
from time import sleep

try:
    import RPi.GPIO as GPIO
except Exception as excep:
    print(excep)

from contextlib import contextmanager

class ServerApp:
    """
    """

    def __init__(self, engine, mailer, intervall = 5):
        self.engine = engine
        self.mailer = mailer
        self.intervall = intervall

        Base.metadata.create_all(self.engine)

        self.create_custom_user()

    @contextmanager
    def __session(self):
        session = scoped_session(sessionmaker(bind = self.engine))
        yield session
        try:
            session.close()
        except Exception as excep:
            print(excep)

    def __conn_client(self, raspi, data):
        """Connect to a RaspberryPi and sends pickled data to it. This will
        usually be a list of sensors, which the Client programm on the
        RaspberryPi will read out. It returns a list of all measurements.

        :param raspi: a Raspi object representing the RaspberryPi to which the
                      connection shall be established.
        :param data: the data that is meant to be send to the RaspberryPi.
                     Usually a list of sensors, which should be read out from
                     the RaspberryPi.

        :return: a list of Measurement objects.
        """

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_socket:
            # Connect to RaspberryPi. Use default port 50000 for this.
            s_socket.connect((raspi.ip, 50000))
            s_socket.sendall(pickle.dumps(data))
            # Wait for the returning data.
            measurements = s_socket.recv(4096)

        return pickle.loads(measurements)

    def create_custom_user(self):

        with self.__session() as session:
            if len(session.query(User).all()) == 0:
                usr = User(username = 'Username',
                           email = 'user@user.de',
                           group = 'luschnig')

                usr.set_password('password')

                session.add(usr)

                try:
                    session.commit()
                except Exception as excep:
                    pass
                else:
                    print('Successfully added user!')

    def __measurement_in_range(self, measurement):
        """Checks whether a measurement is within the currently set range of
        the respective device.

        :param measurement: a Measurement object whose value will be checked.

        :return: bool. ``True`` if the value is within the range, ``False``
                 otherwise.
        """

        if measurement.parameter == 'battery':
            return measurement.value < 20

        with self.__session() as session:
            rg = session.query(Range).get((measurement.device,
                                           measurement.parameter))

        return rg.lower <= measurement.value <= rg.upper

    def __compose_msg(self, measurement):
        """Composes an alert message from a measurement that was previously
        detected to contain an out-of-the-range value.

        :param measurement: a Measurement object.

        :return: a `string` that contains the alert message to be send.
        """

        with self.__session() as session:
            dv = session.query(Device).get(measurement.device)
            rg = session.query(Range).get((measurement.device,
                                           measurement.parameter))

        if measurement.parameter == 'battery':
            return 'Battery of sensor {sid} in {type} {did} (room {room}) is low!'.\
                        format(sid = measurement.sensor,
                               type = dv.type,
                               did = dv.id,
                               room = dv.room)

        INTRO = ' '.join(['The Senseye system has measured a value that is',
                          'out of the range previously set for the respective',
                          'device. The following device is affected:\n'])

        DEV = '{type} (ID: {id}) in room {room}.'.format(type = dv.type,
                                                         id = dv.id,
                                                         room = dv.room)

        MSR = '{time}: {param}: {val} (allowed: {low} - {up})'.\
                format(time = measurement.time,
                       param = measurement.parameter,
                       val = measurement.value,
                       low = rg.lower,
                       up = rg.upper)

        return '\n'.join([INTRO, DEV, MSR])

    def __send_alert(self, measurement):
        """Sends an email to all members of the group the device belongs to, in
        which the the problematic value was measured.

        :param measurement: a Measurement object, whose value is out of range.
        """

        # Query all necessary data from the database.
        with self.__session() as session:
            dv = session.query(Device).get(measurement.device)
            usr = session.query(User).filter(User.group == dv.group)
            rcp = [user.email for user in usr]

        # Send emails to the group members.
        self.mailer.send_msg(recipients = rcp,
                             subject = 'Senseye Alert',
                             message = self.__compose_msg(measurement))

    def check_pi(self, raspi):
        """Checks all sensors attached to a RaspberryPi. The measurements will
        be checked and inserted into the database. In case of measurements
        outside the set range an alert message will be composed and send to all
        email addresses of the group.

        :param raspi: a Raspi object that represents the RaspberryPi to be
                      checked or an integer representing the id of the
                      RaspberryPi.
        """

        if isinstance(raspi, int):
            with self.__session() as session:
                raspi = session.query(RaspberryPi).get(raspi)

        with self.__session() as session:
            sensors = session.query(Sensor).\
                              filter(and_(Sensor.device != None,
                                          Sensor.raspi == raspi.id))
            sensors = [sensor for sensor in sensors]

        measurements = self.__conn_client(raspi, sensors)

        # Try to insert the measurements into the database. If successfull
        # check the measurements and if needed send an alert email.
        for measurement in measurements:
            with self.__session() as session:
                rg = session.query(Range).get((measurement.device,
                                               measurement.parameter))
                if not rg and measurement.parameter != 'battery':
                    continue
                try:
                    session.add(measurement)
                    session.commit()
                except Exception as excep:
                    print(excep)
                    session.rollback()
                else:
                    if not self.__measurement_in_range(measurement):
                        print('ALERT')
                        self.__send_alert(measurement)
                    else:
                        print('All fine!')

    def check_all_pis(self):
        """Queries a list of all RaspberryPis from the database and creates a
        thread for each (to avoid long waiting times) in order to request the
        latest measurements from the sensors attached to each RaspberryPi.
        """

        with self.__session() as session:
            raspis = session.query(RaspberryPi).all()
            ids = [raspi.id for raspi in raspis]

        threads = [Thread(target = self.check_pi, args = (rid,)) for rid in ids]

        for thread in threads:
            thread.start()

    def run(self):
        while True:
            print(datetime.now(), ': Checking.')
            self.check_all_pis()
            sleep(self.intervall*60)


class ClientApp:

    def __init__(self, port = 50000, mode = 'production'):
        self.port = port
        self.mode = mode

    def read_sensors(self, sensors):
        measurements = []
        for sensor in sensors:
            if self.mode == 'production':
                measures = sensor.measure()
            elif self.mode == 'mockup':
                measures = sensor.measure_mockup()

            for measure in measures:
                measurements.append(measure)
        return measurements

    def run(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.OUT)
        GPIO.setup(27, GPIO.OUT)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as c_socket:
            c_socket.bind(('', self.port))

            while True:
                c_socket.listen()
                conn, addr = c_socket.accept()

                with conn:
                    print('Connected by: ',  addr)

                    while True:
                        sensors = conn.recv(4096)
                        if not sensors:
                            break

                        measurements = self.read_sensors(pickle.loads(sensors))
                        conn.sendall(pickle.dumps(measurements))