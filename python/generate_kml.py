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

import numpy as np
import argparse
import csv
import xml

plane_dict = dict()

def csv_to_kml(csv_filename, kml_filename):
    # Read CSV and populate plane dictionary
    reader = csv.reader(open(csv_filename, "r"))
    for row in reader:
        if str(row[0]) == "Date/Time":
            # This row is a header row, ignore it
            continue

        if len(row) < 9:
            # Partial CSV row, discard
            continue

        time_str    = str(row[0])
        timestamp   = int(row[1])
        icao        = str(row[2])
        callsign    = str(row[3])
        alt         = float(row[4])
        speed       = float(row[5])
        heading     = float(row[6])
        lat         = float(row[7])
        lon         = float(row[8])

        add_to_dictionary(time_str, timestamp, icao, callsign, alt, speed, heading, lat, lon)

    # Process dictionary and write KML
    write_kml()

def sqlite_to_kml(db_filename, kml_filename):
    print "To be implemented"


def add_to_dictionary(time_str, timestamp, icao, callsign, alt, speed, heading, lat, lon):
    if plane_dict.has_key(icao) == False:
        # Add this plane to the dictionary
        plane_dict[icao] = dict(callsign=callsign, time=[(timestamp, time_str)], position=[[lon, lat, alt]], heading=[[speed, heading]])
    else:
        # Update this plane's log
        if plane_dict[icao]["callsign"] == "" and callsign != "":
            plane_dict[icao]["callsign"] = callsign

        plane_dict[icao]["time"].append((timestamp, time_str))

        plane_dict[icao]["position"].append([lon, lat, alt])
        # If any values aren't set (NaN), set them to the previous value
        for ii in range(0,len(plane_dict[icao]["position"][-1])):
            if np.isnan(plane_dict[icao]["position"][-1][ii]) == True:
                plane_dict[icao]["position"][-1][ii] = plane_dict[icao]["position"][-2][ii]

        plane_dict[icao]["heading"].append([speed, heading])
        # If any values aren't set (NaN), set them to the previous value
        for ii in range(0,len(plane_dict[icao]["heading"][-1])):
            if np.isnan(plane_dict[icao]["heading"][-1][ii]) == True:
                plane_dict[icao]["heading"][-1][ii] = plane_dict[icao]["heading"][-2][ii]


def write_kml():
    print "To be implemented"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a Google Earth KML file from logged ADS-B data.")
    parser.add_argument("--type", metavar="type", type=str, nargs="+", help="The input file type (csv, sqlite)")
    parser.add_argument("--file", metavar="file", type=str, nargs="+", help="The input filename")
    parser.add_argument("--kml_file", metavar="kml_file", type=str, default="adsb.kml", help="The output KML filename")

    args = parser.parse_args()

    print args.type
    print args.file

    if args.type[0] == "csv":
        print "Reading from CSV file %s" % (args.file[0])
        csv_to_kml(args.file[0], args.kml_file[0])

    elif args.type[0] == "sqlite":
        print "Reading from SQLite database %s" % (args.file[0])
        sqlite_to_kml(args.file[0], args.kml_file[0])

    else:
        print "Invalid argument %s" % (args.type[0])
