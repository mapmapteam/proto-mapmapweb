#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# VideoControl
#
# Copyright 2010 Alexandre Quessy
# http://www.toonloop.com
#
# Toonloop is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Toonloop is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the gnu general public license
# along with Toonloop.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Main GUI of the application.
 * GST pipeline
 * GTK window
 * VJ conductor

Pipeline::
  
  filesrc -> decodebin -> videoscale -> queue -> alpha -> videomixer -> ffmpegcolorspace -> xvimagesink
  filesrc -> decodebin -> videoscale -> queue -> alpha -/

"""
# Import order matters !!!
import os
import sys
#import glob
#from twisted.internet import gtk2reactor
#gtk2reactor.install() # has to be done before importing reactor and gtk
from twisted.internet import reactor
from twisted.internet import task
#import pygtk
#pygtk.require('2.0')
import gobject
gobject.threads_init()
import pygst
pygst.require('1.0')
import gst
import gst.interfaces
import gtk
gtk.gdk.threads_init()
from vctrl import sig
from vctrl import ramp

class VideoPlayer(object):
    """
    Video player.
    """
    def __init__(self, videowidget):
        self._filesrc0_location = None
        self._filesrc1_location = None
        self._videosource_index = 0

        #self._is_playing = False
        # Pipeline
        self._pipeline = gst.Pipeline("pipeline")
        # TODO: use the mixer's pad's alpha prop instead of the alpha elements, and get rid of the alpha elements

        # Source 0:
        self._videotestsrc0 = gst.element_factory_make("videotestsrc", "_videotestsrc0")
        self._xvimagesink0 = gst.element_factory_make("xvimagesink", "_xvimagesink0")
        self._pipeline.add_many(self._videotestsrc0, self._xvimagesink0)
        gst.element_link_many.add_many(self._videotestsrc0, self._xvimagesink0)

        # Manage Gtk+ widget:
        self._videowidget = videowidget


    def set_videotestsrc_pattern(self, pattern):
        """
        @param pattern: number
        """        
        self._videotestsrc0.set_property("pattern", pattern)

    def on_sync_message(self, bus, message):
        #print("on_sync_message %s %s", (bus, message))
        if message.structure is None:
            return
        if message.structure.get_name() == 'prepare-xwindow-id':
            # Sync with the X server before giving the X-id to the sink
            gtk.gdk.threads_enter()
            gtk.gdk.display_get_default().sync()
            self._videowidget.set_sink(message.src)
            message.src.set_property('force-aspect-ratio', True)
            gtk.gdk.threads_leave()
            
    def stop(self):
        self._pipeline.set_state(gst.STATE_NULL)
        gst.info("stopped")

    def play(self):
        self._pipeline.set_state(gst.STATE_PLAYING)

    
class VideoWidget(gtk.DrawingArea):
    """
    Gtk+ widget to display video in.
    """
    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.imagesink = None
        self.unset_flags(gtk.DOUBLE_BUFFERED)

    def do_expose_event(self, event):
        if self.imagesink:
            self.imagesink.expose()
            return False
        else:
            return True

    def set_sink(self, sink):
        assert self.window.xid
        self.imagesink = sink
        self.imagesink.set_xwindow_id(self.window.xid)


def create_empty_cursor():
    pix_data = """/* XPM */
    static char * invisible_xpm[] = {
    "1 1 1 1",
    "       c None",
    " "};"""
    color = gtk.gdk.Color()
    pix = gtk.gdk.pixmap_create_from_data(None, pix_data, 1, 1, 1, color, color)
    return gtk.gdk.Cursor(pix, pix, color, color, 0, 0)


class PlayerApp(object):
    """
    The GUI window to display video in.
    """
    UPDATE_INTERVAL = 500
    def __init__(self):
        self.key_pressed_signal = sig.Signal()
        self.is_fullscreen = False
        # window
        self.window = gtk.Window()
        self.window.set_default_size(410, 325)

        # invisible cursor:
        self.invisible_cursor = create_empty_cursor()
        
        # videowidget and button box
        vbox = gtk.VBox()
        self.window.add(vbox)
        self._video_widget = VideoWidget()
        self._video_widget.connect_after('realize', self._video_widget_realize_cb)
        vbox.pack_start(self._video_widget)

        
        # player
        self._video_player = VideoPlayer(self._video_widget)
        #self._video_player.eos_callbacks.append(self.on_video_eos)
        
        # window events
        self.window.connect("key-press-event", self.on_key_pressed)
        self.window.connect("window-state-event", self.on_window_state_event)
        self.window.connect('delete-event', self.on_delete_event)

    def get_video_player(self):
        """
        Getter.
        So that we avoid public attributes.
        """
        return self._video_player

    def get_gtk_window(self):
        """
        Getter.
        So that we avoid public attributes.
        """
        return self.window

    def on_delete_event(self, *args):
        self._video_player.stop()
        reactor.stop()
    
    def quit(self):
        self._video_player.stop()
        reactor.stop()
    
    def on_key_pressed(self, widget, event):
        """
        Escape toggles fullscreen mode.
        """
        name = gtk.gdk.keyval_name(event.keyval)
        # We want to ignore irrelevant modifiers like ScrollLock
        control_pressed = False
        ALL_ACCELS_MASK = (gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK | gtk.gdk.MOD1_MASK)
        #keyval, egroup, level, consumed = keymap.translate_keyboard_state(event.hardware_keycode, event.state, event.group)
        if event.state & ALL_ACCELS_MASK == gtk.gdk.CONTROL_MASK:
            control_pressed = True
            # Control was pressed
        if name == "Escape":
            self.toggle_fullscreen()
        else:
            if control_pressed:
                if name == "q":
                    self.quit()
        return True
    
    def toggle_fullscreen(self):
        """
        Toggles the fullscreen mode on/off.
        """
        if self.is_fullscreen:
            self.window.unfullscreen()
        else:
            self.window.fullscreen()

    def on_window_state_event(self, widget, event):
        """
        Called when toggled fullscreen.
        """
        self.is_fullscreen = event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN != 0
        if self.is_fullscreen:
            self.window.window.set_cursor(self.invisible_cursor)
        else:
            self.window.window.set_cursor(None)
        return True

    def _video_widget_realize_cb(self, *args):
        self._video_player.play()


class VeeJay(object):
    """
    Chooses movie files to play.
    """
    def __init__(self, app, player, configuration):
        """
        @param app: vctrl.gui.PlayerApp instance.
        @param player: vctrl.gui.VideoPlayer instance.
        @param configuration: vctrl.config.Configuration instance.
        """
        self._video_player = player
        self.configuration = configuration
        #app.key_pressed_signal.connect(self._on_key_pressed_signal)


    def play_next_cue(self):
        """
        Skips the player to the next clip. 
        Schedules to be called again later.
        """
        ret = False
        #prev = -1
        _next = 0
        cues = self.get_cues()
        if self._current_cue_index >= (len(cues) - 1):
            _next = 0
        else:
            _next = (self._current_cue_index + 1) % len(cues)
        print("Next cue: %s" % (_next))
        if len(cues) == 0:
            msg = "Not clip to play."
            raise RuntimeError(msg)
        else:
            if len(cues) == 1:
                print("Only one clip to play.")
            self._current_cue_index = _next
            video_cue = cues[self._current_cue_index]
            ret = self._play_cue(video_cue)

            # TODO: duration = video_cue.duration
            # DELAY_BETWEEN_CHANGES = 5.0 # seconds
            # reactor.callLater(DELAY_BETWEEN_CHANGES, self.play_next_cue)
        return ret


# Need to register our derived widget types for implicit event
# handlers to get called.
#gobject.type_register(PlayerWindow)
gobject.type_register(VideoWidget)

