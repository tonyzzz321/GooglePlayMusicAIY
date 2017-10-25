import aiy.assistant.auth_helpers
import aiy.voicehat
from google.assistant.library import Assistant
from google.assistant.library.event import EventType

from google_play_music_player import GooglePlayMusicPlayer

import subprocess
import threading

account = 'email'       # gmail address
password = 'password'   # gmail password of app-specific password (2FA only)


class CustomActionHelper(object):
    def __init__(self, assistant):
        self._assistant = assistant
        self._is_muted = False
        self._music_player = None
        self._music_player_command_list = []
        self._last_executed_command_for_music_player = None

    def perform_action(self, text):
        if text in ['power off the pi', 'turn off the pi']:
            self._assistant.stop_conversation()
            self.power_off_pi()
        elif text == 'reboot the pi':
            self._assistant.stop_conversation()
            self.reboot_pi()
        elif text in ['ip address', 'what\'s my ip']:
            self._assistant.stop_conversation()
            self.say_ip()
        elif text in ['public ip address', 'what\'s my public ip']:
            self._assistant.stop_conversation()
            self.say_public_ip()
        elif text in ['mute the mic', 'mute microphone', 'stop listening']:
            self._assistant.stop_conversation()
            self.mute_mic()
        elif (text in self._music_player_command_list) or ("play" in text):
            self._assistant.stop_conversation()
            self.player_control(text)


    def power_off_pi(self):
        aiy.audio.say('Good bye!')
        subprocess.call('sudo shutdown now', shell=True)

    def reboot_pi(self):
        aiy.audio.say('See you in a bit!')
        subprocess.call('sudo reboot', shell=True)

    def say_ip(self):
        ip_address = subprocess.check_output("hostname -I | cut -d' ' -f1", shell=True)
        aiy.audio.say('My IP address is %s' % ip_address.decode('utf-8'))

    def say_public_ip(self):
        ip_address = subprocess.check_output("curl -s https://ipv4.wtfismyip.com/text", shell=True)
        aiy.audio.say('My public IP address is %s' % ip_address.decode('utf-8'))

    def mute_mic(self):
        self._is_muted = True
        self._assistant.set_mic_mute(self._is_muted)
        aiy.audio.say('Microphone muted')

    def unmute_mic(self):
        if self._is_muted == True:
            self._is_muted = False
            self._assistant.set_mic_mute(self._is_muted)
            aiy.audio.say('Microphone unmuted')

    def player_control(self, command):
        if self._music_player is None:
            self._music_player = GooglePlayMusicPlayer(account, password, shuffle=True)
            self._music_player_command_list = self._music_player.get_command_list()
        message = self._music_player.run_command(command)
        self._last_executed_command_for_music_player = True
        if message is not None:
            aiy.audio.say(message)


    def player_pause_for_command(self):
        self._last_executed_command_for_music_player = False
        if self._music_player is not None:
            self._music_player.pause_for_command()

    def player_resume_after_command(self):
        if self._music_player is not None:
            self._music_player.resume_after_command(not self._last_executed_command_for_music_player)
