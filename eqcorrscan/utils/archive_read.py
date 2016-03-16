"""
Helper functions for reading data from archives for the EQcorrscan package.

.. note:: These functions are tools to aid simplification of general scripts, \
    they do not cover all use cases, however if you have a use case you want \
    to see here, then let the authors know, or implement it yourself and \
    contribute it back to the project.

Copyright 2015 Calum Chamberlain

This file is part of EQcorrscan.

    EQcorrscan is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    EQcorrscan is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with EQcorrscan.  If not, see <http://www.gnu.org/licenses/>.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


def read_data(archive, arc_type, day, stachans):
    """
    Function to read the appropriate data from your archive for your selected \
    day.

    :type archive: str
    :param archive: The archive source - if arc_type is seishub, this should \
        be a url, if the arc_type is FDSN then this can be either a url or a \
        known obspy client.
    :type arc_type: str
    :param arc_type: The type of archive, can be: seishub, FDSN, day_vols
    :type day: datetime.date
    :param day: Date to retrieve data for
    :type stations: list of tuple
    :param station: Stations and channels to try and get, will not fail if \
        stations are not available, but will warn.

    :returns: obspy.Stream

    .. note:: A note on arc_types, if arc_type is day_vols, then this will \
        look for directories labelled in the IRIS DMC conventions of \
        Yyyyy/Rjjj.01/... where yyyy is the year and jjj is the julian day. \
        Data within these files directories should be stored as day-long, \
        single-channel files.  This is not implemented in the fasted way \
        possible to allow for a more general situation.  If you require more \
        speed you will need to re-write this.
    """
    import obspy
    if arc_type.lower() == 'seishub':
        if int(obspy.__version__.split('.')[0]) >= 1:
            from obspy.clients.seishub import Client
        else:
            from obspy.seishub import Client
    else:
        if int(obspy.__version__.split('.')[0]) >= 1:
            from obspy.clients.fdsn import Client
        else:
            from obspy.fdsn import Client
    from obspy import read, UTCDateTime
    import warnings

    st = []
    available_stations = _check_available_data(archive, arc_type, day)
    for station in stachans:
        if station not in available_stations:
            msg = ' '.join([station[0], station[1], 'is not available for',
                            day.strftime('%d/%m/%Y')])
            warnings.warn(msg)
            continue
        if arc_type.lower() in ['seishub', 'fdsn']:
            client = Client(archive)
            st += client.waveform.getWaveform('*', station[0], '*',
                                              station[1], UTCDateTime(day),
                                              UTCDateTime(day) + 86400)
        elif arc_type.lower() == 'day_vols':
            wavfiles = _get_station_file(os.path.join(archive,
                                                      day.strftime('Y%Y' +
                                                                   os.sep +
                                                                   'R%j.01')),
                                         station[0], station[1])
            for wavfile in wavfiles:
                st += read(wavfile)
    return st


def _get_station_file(path_name, station, channel, debug=0):
    """
    Helper function to find the correct file.

    :type path_name: str
    :param path_name: Path to files to check.
    :type station: str
    :type channel: str

    :returns: list of filenames, str
    """
    import glob
    import os
    from multiprocessing import Pool, cpu_count
    pool = Pool(processes=cpu_count())
    wavfiles = glob.glob(path_name + os.sep + '*')
    out_files = []

    results = [pool.apply_async(_parallel_checking_loop,
                                args=(wavfile, station, channel, debug))
               for wavfile in wavfiles]
    pool.close()
    out_files = [p.get() for p in results]
    pool.join()
    out_files = list(set(out_files))
    return out_files


def _parallel_checking_loop(wavfile, station, channel, debug=0):
    """
    Inner loop for parallel
    """
    from obspy import read
    if debug > 1:
        print('Checking ' + wavfile)
    st = read(wavfile, headonly=True)
    for tr in st:
        if tr.stats.station == station and tr.stats.channel == channel:
            return wavfile


def _check_available_data(archive, arc_type, day):
    """
    Function to check what stations are available in the archive for a given \
    day.

    :type archive: str
    :param archive: The archive source
    :type arc_type: str
    :param arc_type: The type of archive, can be:
    :type day: datetime.date
    :param day: Date to retrieve data for

    :returns: list of tuples of (station, channel) as available.
    """
