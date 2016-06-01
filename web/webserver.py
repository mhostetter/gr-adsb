#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2016 Matt Hostetter.
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

from flask import Flask, request
from flask_socketio import SocketIO, emit
from threading import Thread
import time 
import zmq
import json

HTTP_PORT   = 5000
ZMQ_PORT    = 5001

app = Flask(__name__, static_url_path="")
# app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app)


def background_thread():
    # Establish ZMQ context and socket
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    socket.connect("tcp://127.0.0.1:%d" % (ZMQ_PORT))

    while True:
        # Receive decoded ADS-B message from the decoder over ZMQ
        json_str = socket.recv()

        # Don't know why I need to remove 3 characters from the beginning of this string, but I do
        json_str = json_str[3:]

        # Convert JSON string into Python dictionary
        plane = json.loads(json_str)

        # Handle ZMQ message: either update the plane on the client or remove it from the page
        if (plane["msg_type"] == "updatePlane"):
            socketio.emit("updatePlane", plane)

        elif (plane["msg_type"] == "removePlane"):
            socketio.emit("removePlane", plane)

        else:
            print "Unknown ZMQ message: %s" % (msg)

        time.sleep(0.100)


@app.route("/")
def index():
    return app.send_static_file("index.html")


@socketio.on("connect")
def connect():
    print("Client connected", request.sid)


@socketio.on("disconnect")
def disconnect():
    print("Client disconnected", request.sid)


if __name__ == "__main__":
    thread = Thread(target=background_thread)
    thread.daemon = True
    thread.start()

    socketio.run(app, host="127.0.0.1", port=HTTP_PORT, debug=True)
