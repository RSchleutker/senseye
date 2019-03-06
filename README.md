# Senseye

Senseye is a python library for setting up a Bluemeastro sensor monitoring system.

## Getting started

### Prerequisites

* Python 3
* pip
* wheels

Additionally you need the proper hardware:

* At least one Bluemaestro sensor to read out.
* A Raspberry Pi with bluetooth somewhere nearby the sensor.
* A central computer (can also be a Raspberry Pi).

### Installing

To get started download the `senseye-x.x-py3-none-any.whl` file from the `dist/` folder and install the library by running

```
pip install senseye-x.x-py3-none-any.whl
```

on both, the Raspberry Pi used to read out the sensors and the central computer. This will add the `senseye` library to your python libraries. Alternatively, if you want to use the code for your own customized project download the whole source cdoe and use it for development.

### Setting up

The idea is to setup a script on each Raspberry Pi that listens to incoming connections upon which it will read out the sensors send to it by this connection. In return it will send back a list of measurements that the central script will insert into the database.

Setting up the Raspberry Pi is as simple as saving and running the following lines

```
from senseye.app import ClientApp

ClientApp(port = 50000).run()
```

This will start the script that listens for connections on port `50000`.

To setup the central computer save and run the following script

```
from senseye.app import ServerApp
from senseye.mailer import Mailer
from sqlalchemy import create_engine

ENGINE = create_engine('sqlite:///senseye.db')
MAILER = Mailer(server = '<email server>',
                name = '<email name>',
                password = '<email password>',
                email_address = '<email address>')

server_app = ServerApp(ENGINE, MAILER, intervall = 5)
server_app.run()
```

This automatically creates an SQLite database called `senseye.db` with an User called `User` and password `password`. This login data can be used for the dashboard. The script will now connect to all Raspberry Pis in the local network defined in the database every `5` minutes.