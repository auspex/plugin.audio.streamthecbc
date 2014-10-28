#! /usr/bin/python
# -*- coding: UTF-8 -*-

from xbmcswift2 import Plugin, CLI_MODE, xbmc
from BeautifulSoup import BeautifulSoup, SoupStrainer
from urllib import urlopen
from time import gmtime
import sys
import os
from constants import *

if CLI_MODE:
    CBC_STREAMS_URL = 'example/menuAllStreams.html'
else:
    CBC_STREAMS_URL = 'http://www.cbc.ca/liveradio/snippets/menuAllStreams.html'

log = lambda x: plugin.log.info(x)

plugin = Plugin()
try:
    profile     = plugin.addon.getAddonInfo('profile')
    stream_path = xbmc.translatePath(profile).decode('utf-8')
    log(profile)
    log(stream_path)
except: # if it's not a "special://" path, then we must be running in the xbmcswift2 CLI  
    stream_path = os.path.dirname(plugin.storage_path.rstrip('/'))
    log(stream_path)

@plugin.route('/')
def index():
    items = [
             {'label': _('CBC Radio 1'), 'path': plugin.url_for('channel',channel='radio1')},
             {'label': _('CBC Radio 2'), 'path': plugin.url_for('channel',channel='radio2')},
             {'label': _('CBC Radio 3'), 'path': plugin.url_for('stream', channel='radio3', url=R3_WEB), 'is_playable':True},
             {'label': _('CBC Music'),   'path': plugin.url_for('channel',channel='music')},
             ]
    refresh_channels() 
    return items


@plugin.route('/channel/<channel>')
def channel(channel):
    """
    Get the list of currently playing programs from the CBC 
    (it will be cached until the half-hour, as programs only change that often).
    Then 
    """
    programs = refresh_channels()
    
    items = [{'label': key, 
              'path': plugin.url_for('stream', 
                                     channel=channel, 
                                     url=programs[key]['url']), 
              'is_playable':True,
              } for key in programs if programs[key]['channel'] == channel]
    return items


def refresh_channels():
    """
    >>> programs = plugin.get_storage('programs', file_format='json', )
    >>> print dir(programs)
    True
    
    """
    current_time = gmtime().tm_min % 30
    # The program info for Radio 1 changes on the half-hour, so cache until a minute past the half
    programs = plugin.get_storage('programs', file_format='json', TTL=31-current_time)
    # so much for acting like a dict: I have to coerce it to be able to test for emptiness
    # TODO: remove coercion when my commit is accepted at xbmcswift2
    if not dict(programs):
        # there should be three <div> tags for the different types of URL
        channels = list(BeautifulSoup(urlopen(CBC_STREAMS_URL), parseOnlyThese=SoupStrainer('div','network')))

        # for each <li> tag in a <div class="network"> section, add it to a dictionary by program name/timezone
        # (this means that if a program is available on different streams, we'll only care about
        # multiple streams if they run at different times — might want to ignore Labrador, as it uses
        # AT but everything runs half an hour earlier than Newfoundland [ie, the same actual time])
        for ix,channel in enumerate(channels):
            programs = build_stream_list(CHANNEL_LIST[ix], channel.findAll('li', 'stream'), programs)
    return programs
            

def build_stream_list(channel, stream_list, programs):         
    for item in stream_list:
        # key is (program,timezone') if we have them (for Radio1/Radio2)
        # otherwise it's the label attached to the URL
        metadata = item.span
        filename = item.find('label', 'url').text
        if metadata:
            key = u'{0}/{1}'.format(metadata.label.text, metadata.b.text)
        else:
            key = filename
            
        # TODO: replace __contains__ with correct has_key(), when my commit is accepted at xbmcswift2
        if not programs.__contains__(key):
            urls = [x.attrMap['href'] for x in item.findAll('a', 'url')]
            if 'radio3' in urls[0]:
                programs[key] = {'channel':'radio3', 'url':R3_WEB}
                urls[0]       = R3_WEB
            else:
                # high quality streams are the default (but only radio 1 has "low quality" streams)
                if channel == 'radio1': 
                    if plugin.get_setting('hq_streams',bool):
                        quality = 'H'
                    else:
                        quality = 'L'
                    try:
                        url_index = QUALITY.index(quality)
                    except: # should only be IndexError
                        url_index = 0
                else:
                    url_index = 0
                
                programs[key] = {'channel':channel, 'url':urls[url_index]}
        
    return programs

@plugin.route('/stream/<channel>/<url>')
def stream(channel, url):
    log("stream URL: "+url)
    plugin.set_resolved_url(url)

def _(string_id):
    try:
        return plugin.get_string(STRINGS[string_id])
    except: # I think there are two possible exceptions here 
        log('String is missing: %s' % string_id)
        return string_id


if __name__ == '__main__':
    # if there are arguments to the command line, we should be IN XBMC/Kodi
    if len(sys.argv) > 1:
        plugin.run()
    # otherwise we need to start up xbmcswift2
    else:
        from xbmcswift2.cli import cli
        sys.argv.append('run')
        cli.main()
