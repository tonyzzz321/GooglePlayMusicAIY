#!/usr/bin/env python3

from gmusicapi import Mobileclient
from vlc import EventType, Instance
import json
import os.path
import sys
import random

available_commands = {
    'resume': 'play',
    'pause': 'pause',
    'stop': 'stop',
    'next': 'next',
    'previous': 'previous',
    'shuffle on': 'shuffle on',
    'shuffle off': 'shuffle off',
    'shuffle status': 'shuffle status',
    'looping off': 'looping off',
    'looping all': 'looping all',
    'looping one': 'looping one',
    'looping status': 'looping status',
    'volume up': 'volume up',
    'volume down': 'volume down',
    'mute': 'mute',
    'unmute': 'unmute'
}

class GooglePlayMusicPlayer(object):
    def __init__(self, account, password, shuffle=False, loop=0, volume=50, muted=False, library_update=False, debug=False):
        self._api = Mobileclient(debug_logging=False)
        self._vlc = Instance()

        self._library_songs = None
        self._library_playlists = None

        self._queue_trackDict = []
        self._queue_index = -99          # -1 = finished playing queue, -99 = empty queue, -2 = fresh start
        self._queue_history_backward = []
        self._queue_history_forward = []
        self._queue_shuffle_on = shuffle
        self._queue_loop_mode = loop     # 0 = loop off, 1 = loop all, 2 = repeat one

        self._player = None
        self._player_state = 'stopped'  # stopped, playing, or paused
        self._player_volume = volume
        self._player_volume_muted = muted

        self._command_dict = available_commands
        self._id_text = '[GooglePlayMusicPlayer] '
        self._is_playing_before_pausing_for_command = False
        self._last_executed_command = 'stop'
        self._debug = debug

        self._api.login(account, password, Mobileclient.FROM_MAC_ADDRESS)
        self._library_load_data(library_update)


    ### LIBRARY Functions ###
    def _library_load_data(self, force_online=False):
        if (not force_online) and os.path.isfile('songs.json'):
            # Load from file
            if self._debug is True: print(self._id_text + 'Found local song data.')
            with open('songs.json') as input_file:
                self._library_songs = json.load(input_file)
        else:
            self._library_songs = self._api.get_all_songs()
            # Save to file
            with open('songs.json', 'w') as output_file:
                json.dump(self._library_songs, output_file)

        if (not force_online) and os.path.isfile('playlists.json'):
            # Load from file
            if self._debug is True: print(self._id_text + 'Found local playlist data.')
            with open('playlists.json') as input_file:
                self._library_playlists = json.load(input_file)
        else:
            self._library_playlists = self._api.get_all_user_playlist_contents()
            # Save to file
            with open('playlists.json', 'w') as output_file:
                json.dump(self._library_playlists, output_file)

    def _library_get_song_details(self, track_id):
        for song_dict in self._library_songs:
            if track_id == song_dict['id']:
                return song_dict['artist'] + " - "+ song_dict['title']
        return "Unknown Artist - Unknown Title"

    ### End LIBRARY Functions ###


    ### QUEUE Functions ###
    def _queue_load_playlist(self, playlist):
        playlist_name = playlist.strip().lower()
        self._queue_reset()
        
        for playlist_dict in self._library_playlists:
            actual_playlist_name = playlist_dict['name'].strip().lower()
            if playlist_name in actual_playlist_name:
                if self._debug is True: print(self._id_text + "Found match...", playlist_dict['name'])
                for track_dict in playlist_dict['tracks']:
                    self._queue_trackDict.append(track_dict)
                if len(self._queue_trackDict) != 0:
                    self._queue_index = -2
                return playlist_dict['name']
            else:
                if self._debug is True: print(self._id_text + "Found...", playlist_dict['name'])
        if self._debug is True: print(self._id_text + "Nothing matches... Playlist was not loaded...")
        return None

    def _queue_reset(self):
        self._controller_stop()
        self._queue_trackDict = []
        self._queue_index = -99
        self._queue_history_backward = []
        self._queue_history_forward = []

    def _queue_reset_index(self):
        if self._queue_shuffle_on is True:
            self._queue_index = self._queue_random_index()
        else:
            self._queue_index = 0

    def _queue_reset_history(self):
        self._queue_history_backward = []
        self._queue_history_forward = []

    def _queue_random_index(self):
        while True:
            random_number = random.randrange(0, len(self._queue_trackDict))
            if (self._queue_index != random_number) or (len(self._queue_trackDict) == 1):
                break
        return random_number

    def _queue_next(self):
        if len(self._queue_trackDict) == 0:
            self._queue_index = -99
            return

        if self._queue_loop_mode == 2:   # repeat one
            return

        if self._queue_shuffle_on is True:
            self._queue_history_backward.append(self._queue_index)
            if len(self._queue_history_forward) > 0:
                self._queue_index = self._queue_history_forward.pop()
            else:
                self._queue_index = self._queue_random_index()
        else:
            self._queue_index += 1
            if (self._queue_index >= len(self._queue_trackDict)) and (self._queue_loop_mode == 0):
                self._queue_index = -1
            else:
                self._queue_index %= len(self._queue_trackDict)

    def _queue_previous(self):
        if len(self._queue_trackDict) == 0:
            self._queue_index = -99
            return

        if self._queue_shuffle_on is True:
            if len(self._queue_history_backward) > 0:
                self._queue_history_forward.append(self._queue_index)
                self._queue_index = self._queue_history_backward.pop()
        else:
            self._queue_index = max(0, self._queue_index - 1)

    def _queue_get(self):
        if self._queue_index == -2:
            self._queue_reset_index()
            return self._queue_get()
        if self._queue_index == -1:
            self._queue_reset_index()
            return None
        if (self._queue_index < 0) or (self._queue_index >= len(self._queue_trackDict)):
            return None
        return self._queue_trackDict[self._queue_index]

    ### End QUEUE Functions ###


    ### PLAYER & CONTROLLER Functions ###
    def _controller_play_song(self, song_dict):
        stream_url = self._api.get_stream_url(song_dict['trackId'])
        self._player = self._vlc.media_player_new()
        media = self._vlc.media_new(stream_url)
        self._player.set_media(media)
        if self._player_volume_muted is True:
            self._player.audio_set_volume(0)
        else:
            self._player.audio_set_volume(self._player_volume)
        self._player.play()
        self._player_state = 'playing'

        self._player.event_manager().event_attach(EventType.MediaPlayerEndReached, self._controller_finish_and_play_next)

        song_info_string = self._library_get_song_details(song_dict['trackId'])
        print(self._id_text + "Playing... " + song_info_string + " (" + song_dict['id'] + ")")

    def _controller_play(self):
        if self._player_state == 'stopped':
            song_dict = self._queue_get()
            if song_dict == None:
                return
            self._controller_play_song(song_dict)
        elif self._player_state == 'playing':
            return
        elif self._player_state == 'paused':
            self._player.set_pause(0)
            self._player_state = 'playing'

    def _controller_pause(self):
        if self._player_state == 'playing':
            self._player.set_pause(1)
            self._player_state = 'paused'

    def _controller_stop(self):
        if self._player_state in ['playing', 'paused']:
            self._player.stop()
            self._player_state = 'stopped'

    def _controller_finish_and_play_next(self, event):
        self._player_state = 'stopped'
        self._api.increment_song_playcount(self._queue_trackDict[self._queue_index]['id'])
        self._controller_next()
        self._controller_play()

    def _controller_next(self):
        saved_player_state = self._player_state
        self._controller_stop()
        self._queue_next()
        if saved_player_state != 'stopped':
            self._controller_play()

    def _controller_previous(self):
        saved_player_state = self._player_state
        self._controller_stop()
        self._queue_previous()
        if saved_player_state != 'stopped':
            self._controller_play()

    def _controller_shuffle(self, mode):    # mode False = off, mode True = on
        self._queue_shuffle_on = mode
        self._queue_reset_history()

    def _controller_loop(self, mode):   # mode 0 = loop off, mode 1 = loop all, mode 2 = repeat one
        self._queue_loop_mode = mode

    def _controller_volume_adjust(self, direction, amount):
        if direction is 'up':
            self._player_volume = min(self._player_volume + amount, 100)
        else:
            self._player_volume = max(0, self._player_volume - amount)

        if self._player is not None:
            self._player.audio_set_volume(self._player_volume)
        self._player_volume_muted = False

    def _controller_volume_mute(self):
        if self._player_volume_muted is False:
            if self._player is not None:
                self._player.audio_set_volume(0)
            self._player_volume_muted = True

    def _controller_volume_unmute(self):
        if self._player_volume_muted is True:
            if self._player is not None:
                self._player.audio_set_volume(self._player_volume)
            self._player_volume_muted = False

    ### End PLAYER & CONTROL Functions ###



    def load_playlist(self, playlist_name):
        self._last_executed_command = 'load'
        return self._queue_load_playlist(playlist_name)

    def play(self):
        self._last_executed_command = 'play'
        self._controller_play()

    def pause(self):
        self._last_executed_command = 'pause'
        self._controller_pause()

    def stop(self):
        self._last_executed_command = 'stop'
        self._controller_stop()

    def next(self):
        self._last_executed_command = 'next'
        self._controller_next()

    def previous(self):
        self._last_executed_command = 'previous'
        self._controller_previous()

    def shuffle(self, command):
        self._last_executed_command = 'shuffle'
        if command in [0, 1]:
            self._controller_shuffle(True if command is 1 else False)
        elif command is 2:
            return self._queue_shuffle_on

    def loop(self, command):
        self._last_executed_command = 'loop'
        if command in [0, 1, 2]:
            self._controller_loop(command)
        elif command is 3:
            return self._queue_loop_mode

    def volume_adjust(self, direction, amount):
        self._last_executed_command = 'volume'
        if direction in ['up', 'down']:
            self._controller_volume_adjust(direction, amount)

    def mute(self):
        self._last_executed_command = 'mute'
        self._controller_volume_mute()

    def unmute(self):
        self._last_executed_command = 'unmute'
        self._controller_volume_unmute()


    def get_command_list(self):
        return self._command_dict.keys()

    def pause_for_command(self):
        if self._player_state is 'playing':
            self._is_playing_before_pausing_for_command = True
            self._controller_pause()
        else:
            self._is_playing_before_pausing_for_command = False

    def resume_after_command(self, force):
        if self._is_playing_before_pausing_for_command is True:
            if (force is True) or (self._last_executed_command not in ['play', 'pause', 'stop']):
                self._controller_play()


    # from google assistant voice command control (import this file from google AIY)
    def run_command(self, action):
        if 'play' in action:
            playlist = action.replace("play", "").strip()
            if self.load_playlist(playlist) is None:
                return ('I am not able to find ' + playlist)
            self.play()
        elif self._command_dict[action] == 'play':
            self.play()
        elif self._command_dict[action] == 'pause':
            self.pause()
        elif self._command_dict[action] == 'stop':
            self.stop()
        elif self._command_dict[action] == 'next':
            self.next()
        elif self._command_dict[action] == 'previous':
            self.previous()
        elif self._command_dict[action] == 'shuffle off':
            self.shuffle(0)
        elif self._command_dict[action] == 'shuffle on':
            self.shuffle(1)
        elif self._command_dict[action] == 'shuffle status':
            s = 'on' if self.shuffle(2) is True else 'off'
            return ('Shuffle is ' + s)
        elif self._command_dict[action] == 'looping off':
            self.loop(0)
        elif self._command_dict[action] == 'looping all':
            self.loop(1)
        elif self._command_dict[action] == 'looping one':
            self.loop(2)
        elif self._command_dict[action] == 'looping status':
            s = self.loop(3)
            msg = 'is off' if s is 0 else ('all songs' if s is 1 else 'this song')
            return ('looping ' + msg)
        elif self._command_dict[action] == 'volume up':
            self.volume_adjust('up', 10)
        elif self._command_dict[action] == 'volume down':
            self.volume_adjust('down', 10)
        elif self._command_dict[action] == 'mute':
            self.mute()
        elif self._command_dict[action] == 'unmute':
            self.unmute()
        else:   # probably won't get here
            print(self._id_text + 'Not a valid action...')
            return ('I don\'t know what to do.')


# from console text command control (run this file as script in console)
# OUTDATED
def start():
    account = 'email'       # gmail address
    password = 'password'   # gmail password of app-specific password (2FA only)
    
    player = GooglePlayMusicPlayer(account, password, shuffle=True)

    while True:
        print(self._id_text + 'Available action: load <playlist>, play, pause, stop, next, previous, shuffle <on | off>, loop <off | all | one>, volume <up | down>, mute, unmute, exit')
        action = input(self._id_text + 'Enter a control action: ')

        if 'load' in action:
            playlist = action.replace("load", "").strip()
            player.load_playlist(playlist)
        elif action == 'play':
            player.play()
        elif action == 'pause':
            player.pause()
        elif action == 'stop':
            player.stop()
        elif action == 'next':
            player.next()
        elif action == 'previous':
            player.previous()
        elif action == 'shuffle off':
            player.shuffle(0)
        elif action == 'shuffle on':
            player.shuffle(1)
        elif action == 'shuffle status':
            player.shuffle(2)
        elif action == 'loop off':
            player.loop(0)
        elif action == 'loop all':
            player.loop(1)
        elif action == 'loop one':
            player.loop(2)
        elif action == 'loop status':
            player.loop(3)
        elif action == 'volume up':
            player.volume_adjust('up', 10)
        elif action == 'volume down':
            player.volume_adjust('down', 10)
        elif action == 'mute':
            player.mute()
        elif action == 'unmute':
            player.unmute()
        elif action == 'exit':
            sys.exit(0)
        else:
            print(self._id_text + 'Not a valid action...')


if __name__ == '__main__':
    start()
