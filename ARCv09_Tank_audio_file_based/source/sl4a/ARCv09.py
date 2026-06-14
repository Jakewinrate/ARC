#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import BaseHTTPServer
from threading import Thread
import urlparse
import time
import string

try:
    import android
    droid = android.Android()
except ImportError:
    def mediaPlay(path):
        print "PLAY", path

    import mock
    droid = mock.Mock()
    droid.mediaPlay = mediaPlay


HOST_NAME = ''
PORT_NUMBER = 9090
COMMAND_SEND_INTERVAL = 1.0  # seconds
COMMAND_TIMEOUT = COMMAND_SEND_INTERVAL * 2

PAGE_TEMPLATE = string.Template('''
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<style>
		body {
			overflow	: hidden;
			padding		: 0;
			margin		: 0;
			background: url(http://${IP_ADDRESS}:8080/videofeed) no-repeat center center fixed; 
                        -webkit-background-size: contain;
                        -moz-background-size: contain;
                        -o-background-size: contain;
                        background-size: contain;
                        background-color: black;
		}
		#info {
			position	: absolute;
			top		: 0px;
			width		: 100%;
			padding		: 5px;
			text-align	: center;
		}
		#info a {
			color		: #66F;
			text-decoration	: none;
		}
		#info a:hover {
			text-decoration	: underline;
		}
		#container {
			width		: 100%;
			height		: 100%;
			overflow	: hidden;
			padding		: 0;
			margin		: 0;
			-webkit-user-select	: none;
			-moz-user-select	: none;
		}
		</style>
<script src="http://ajax.googleapis.com/ajax/libs/jquery/1.8.3/jquery.min.js"></script>
<script src="http://jeromeetienne.github.com/virtualjoystick.js/virtualjoystick.js"></script>

<script>
$(document).ready(function(){
    function CommandSender(cmdInterval){
        this.cmdInterval = cmdInterval;
        this.lastCmd = "";
        this.lastState = "";
        this.lastTime = new Date();
    }
    CommandSender.prototype.run = function(){
        var $this = this;
        setInterval(function(){
            $this.updateState($this.lastState, $this.lastCmd);
        }, this.cmdInterval);
    }
    CommandSender.prototype.updateState = function(state, cmd){
        if((new Date() - this.lastTime) < this.cmdInterval &&
            cmd == this.lastCmd && state == this.lastState)
            return;
        if (state == "begin" && cmd){
            this.sendCommand(state, cmd);
        }
        else if (state != this.lastState) {
            this.sendCommand("end", cmd);
        }
        this.lastState = state;
        this.lastCmd = cmd;
        this.lastTime = new Date();
    }
    CommandSender.prototype.sendCommand = function(state, cmd){
        $.post('command/' + state + ':' + cmd, function(resp){
            console.log(resp);
        });
    }

    var cmdInterval = ${COMMAND_SEND_INTERVAL};

    (function buttonsHandler(){
        var sender = new CommandSender(cmdInterval);
        $(".btn").mousedown(function(){
            sender.updateState("begin", $(this).data("command"));
        }).mouseup(function(){
            sender.updateState("end", $(this).data("command"));
        }).mouseleave(function(){
            sender.updateState("end", "");
        });
        sender.run();
    })();

    (function keyBoardHandler(){
        var sender = new CommandSender(cmdInterval);
        var arrow = {100: 'left', 104: 'up', 102: 'right', 98: 'down', 97: 'leftdown', 99: 'rightdown', 103: 'leftup', 105: 'rightup'};
        $(document).keydown(function (e) {
            var keyCode = e.keyCode || e.which;
            var cmd = arrow[keyCode];
            if (cmd)
                sender.updateState("begin", cmd);
        }).keyup(function (e) {
            sender.updateState("end", "");
        });
        sender.run();
    })();
    $("#joystickframe").load(function(){
        var container = $('#joystickframe').contents().find('#joystick')[0];
        var joystick  = new VirtualJoystick({
            container : container,
            mouseSupport: true
        });
        var sender = new CommandSender(cmdInterval);
        setInterval(function(){
            var cmd = (joystick.right() ? 'right'  : '')
                    + (joystick.up()    ? 'up'     : '')
                    + (joystick.left()  ? 'left'   : '')
                    + (joystick.down()  ? 'down'   : '');
            var state = (cmd === '' ? 'end' : 'begin');
            sender.updateState(state, cmd);
        }, 1/30 * 1000);
    });

});
</script>
</head>
<body>
<div id="rightcolumn">
   <iframe id="joystickframe" src="joystick.html" webkitallowfullscreen="" mozallowfullscreen="" allowfullscreen="" width="100%" height="100%" frameborder="0"
</iframe>
</div>
</body>
</html>
''')

PAGE_JOYSTICK_TEMPLATE = '''
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, user-scalable=no, minimum-scale=1.0, maximum-scale=1.0">
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<style type="text/css">
    body {
        color: black;
        overflow: hidden;
        padding: 0;
        margin: 0;
    }
    div#joystick {
        color: white;
        width: 100%;
        height: 100%;
        overflow: hidden;
        padding: 0;
        margin: 0;
        -webkit-user-select: none;
        -moz-user-select: none;
    }
</style>
</head>
<body>
<div id="joystick" style="">Joystick area. Press and drag (touch or mouse)</div>
</body>
'''


class CarControllerThread(Thread):

    path_to_audio = '/mnt/sdcard/droid_car/'
    command_to_audio = {
        'up': 'up.wav',
        'down': 'down.wav',
        'left': 'left.wav',
        'right': 'right.wav',
        'rightdown': 'rightdown.wav',
        'leftdown': 'leftdown.wav',
        'rightup': 'rightup.wav',
        'leftup': 'leftup.wav',
    }

    def __init__(self, timeout=1):
        super(CarControllerThread, self).__init__()
        self.timeout = timeout
        self.pool_timeout = timeout / 3.0
        self.current_state = ""
        self.current_command = ""
        self.last_cmd_timestamp = time.time()

    def run(self):
        while True:
            elapsed = time.time() - self.last_cmd_timestamp
            if self.current_state == "begin" and elapsed > self.timeout:
                self.update_state("end", "")
            time.sleep(self.pool_timeout)

    def update_state(self, state, command):
        self.last_cmd_timestamp = time.time()
        if state == self.current_state and command == self.current_command:
            return
        self.current_state = state
        self.current_command = command
        if state == "end":
            print "PAUSE"
            droid.mediaPlaySetLooping(False)
            droid.mediaPlayPause()
        elif state == "begin":
            print "PLAY", command
            audio = self.command_to_audio.get(command)
            if audio:
                droid.mediaPlay(os.path.join(self.path_to_audio, audio))
                droid.mediaPlaySetLooping(True)
            else:
                print "wrong command:", command


class DroidHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        url = urlparse.urlsplit(self.path)

        if url.path == '/joystick.html':
            self.wfile.write(PAGE_JOYSTICK_TEMPLATE)
        else:
            ip, port = self.headers.get('Host').split(":", 2)
            self.wfile.write(
                PAGE_TEMPLATE.safe_substitute(
                    IP_ADDRESS=ip,
                    COMMAND_SEND_INTERVAL=int(COMMAND_SEND_INTERVAL * 1000),
                )
            )

    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        if self.path.startswith("/command/"):
            try:
                #/command/state:up
                state, cmd = self.path.split("/")[-1].split(":")
            except ValueError:
                print "ERROR", self.path
                self.wfile.write("fail")
                return
            controller.update_state(state, cmd)
            self.wfile.write("ok")
        elif self.path.startswith("/ping"):
            self.wfile.write("pong")


controller = CarControllerThread(COMMAND_TIMEOUT)
controller.start()

my_srv = BaseHTTPServer.HTTPServer((HOST_NAME, PORT_NUMBER), DroidHandler)
print 'web server running on port %s' % PORT_NUMBER
my_srv.serve_forever()
