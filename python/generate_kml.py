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
import time
import calendar
import random
import csv
import sqlite3
import xml.etree.ElementTree as ET

plane_dict = dict()

# http://www.colourlovers.com, Papeterie Haute Ville
COLOR_LUT = [0x113f8c, 0x61ae24, 0xd70060, 0x01a4a4, 0xd0d102, 0xe54028, 0x00a1cb, 0x32742c, 0xf18d05, 0x616161]

FT_PER_METER    = 3.28084

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
    write_kml(kml_filename)


def sqlite_to_kml(db_filename, kml_filename):
    # Read database and plot planes
    conn = sqlite3.connect(db_filename)
    conn.text_factory = str
    c = conn.cursor()

    kml = ""
    kml += kml_header()

    # kml += """<LookAt>"""
    # kml += """<gx:TimeSpan>"""
    # kml += """<begin>2010-05-28T02:02:09Z</begin>"""
    # kml += """<end>2010-05-28T02:02:56Z</end>"""
    # kml += """</gx:TimeSpan>"""
    # kml += """</LookAt>"""

    c.execute("SELECT DISTINCT ICAO FROM ADSB;")
    icao_tuples = c.fetchall()

    for icao_tuple in icao_tuples:
        icao = icao_tuple[0]
        print "ICAO Address %s" % (icao)

        c.execute("""SELECT DISTINCT Callsign FROM ADSB WHERE ICAO == "%s";""" % (icao))    
        callsign_tuples = c.fetchall()

        # Find the first non-zero callsign for the plane.  They should all be the same, 
        # so pick the first one and then quit.
        callsign = "?"
        for callsign_tuple in callsign_tuples:
            if callsign_tuple[0] != None:
                callsign = callsign_tuple[0]
                break

        kml += """\n<Placemark>"""
        kml += """\n<name>%s</name>""" % (callsign)
        kml += kml_style(COLOR_LUT[random.randrange(0,len(COLOR_LUT))], 8)
        kml += """\n<gx:Track>"""
        kml += """\n<altitudeMode>relativeToGround</altitudeMode>"""

        c.execute("""SELECT Datetime,Latitude,Longitude,Altitude FROM ADSB WHERE ICAO == "%s" AND Latitude IS NOT NULL""" % (icao))    
        location_tuples = c.fetchall()

        for location_tuple in location_tuples:
            kml += """\n<when>%s</when>""" % (location_tuple[0])

        for location_tuple in location_tuples:
            # NOTE: KML expects the altitude in meters
            kml += """\n<gx:coord>%1.8f %1.8f %1.1f</gx:coord>""" % (location_tuple[2], location_tuple[1], location_tuple[3]/FT_PER_METER)

        kml += """\n</gx:Track>"""
        kml += """\n</Placemark>"""

    
    kml += kml_footer()

    print kml

    f = open(kml_filename, "w")
    f.write(kml)
    f.close()


def kml_header():
    kml = ""
    kml += """<?xml version="1.0" encoding="UTF-8"?>"""
    kml += """\n<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">"""
    kml += """\n<Document>"""
    kml += """\n<name>ADS-B Plane Tracking</name>"""
    kml += """\n<Snippet>Created %s</Snippet>""" % ("blah")
    kml += """\n<Folder>"""
    kml += """\n<name>Planes</name>"""
    
    return kml


def kml_footer():
    kml = ""
    kml += """\n</Folder>"""
    kml += """\n</Document>"""
    kml += """\n</kml>"""

    return kml


def kml_style(color, width):
    kml = ""
    kml += """\n<Style>"""
    kml += """\n<IconStyle>"""
    kml += """\n<Icon>"""
    if 1:
        kml += """\n<href>http://earth.google.com/images/kml-icons/track-directional/track-0.png</href>"""
        kml += """\n<href>/home/matt/repos/kml/plane5.png</href>"""
    kml += """\n</Icon>"""
    kml += """\n</IconStyle>"""
    kml += """\n<LineStyle>"""
    kml += """\n<color>99%06x</color>""" % (color)
    kml += """\n<width>%d</width>""" % (width)
    kml += """\n</LineStyle>"""
    kml += """\n</Style>"""

    return kml


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


def write_kml(kml_filename):
    kml = ET.Element("kml")
    file = ET.Comment(text="Automatically generated using generate_kml.py from the gr-adsb GNU Radio Module.")

    Document = ET.SubElement(kml, "Document")
    
    name = ET.SubElement(Document, "name")
    name.text = "ADS-B Data"
    
    Snippet = ET.SubElement(Document, "Snippet")
    Snippet.text = "Created on %s" % ("Fill this in")

    Folder = ET.SubElement(Document, "Folder")
    
    name = ET.SubElement(Folder, "name")
    name.text = "Planes"

    # Add planes
    for key in plane_dict:
        Placemark = ET.SubElement(Folder, "Placemark")
        name = ET.SubElement(Placemark, "name")
        name.text = "%s : %s" % (key, plane_dict[key]["callsign"])

        gx_Track = ET.SubElement(Placemark, "gx_Track")

        for ii in range(0,len(plane_dict[key]["time"])):
            lon = plane_dict[key]["position"][ii][0]
            lat = plane_dict[key]["position"][ii][0]
            alt = plane_dict[key]["position"][ii][0]

            if np.isnan(lon) == False and np.isnan(lat) == False and np.isnan(alt) == False:
                when = ET.Element("when")
                when.text = plane_dict[key]["time"][ii][1]

                gx_coord = ET.Element("gx_coord")
                gx_coord.text = "%s %s %s" % (
                            "{:12.8f}".format(lon),
                            "{:12.8f}".format(lat),
                            "{:6.1f}".format(alt),
                        )

                gx_Track.append(when)
                gx_Track.append(gx_coord)


    # ET.ElementTree.write(file, encoding="us-ascii", xml_declaration=True, default_namespace=None, method="xml")

    # ET.dump(kml)
    # print ET.tostring(kml, pretty_print=True)
    xml_str = ET.tostring(kml)

    file = open(kml_filename, "w")
    file.write(xml_str)
    file.close()


if __name__ == "__main__":
    # Set up the command-line arguments
    parser = argparse.ArgumentParser(description="Generate a Google Earth KML file from logged ADS-B data.")
    parser.add_argument("--type", metavar="type", type=str, nargs="+", help="The input file type (csv, sqlite)")
    parser.add_argument("--file", metavar="file", type=str, nargs="+", help="The input filename")
    parser.add_argument("--kml_file", metavar="kml_file", type=str, default="adsb.kml", help="The output KML filename")

    args = parser.parse_args()

    if args.type[0] == "csv":
        print "Reading from CSV file %s" % (args.file[0])
        csv_to_kml(args.file[0], args.kml_file)

    elif args.type[0] == "sqlite":
        print "Reading from SQLite database %s" % (args.file[0])
        sqlite_to_kml(args.file[0], args.kml_file)

    else:
        print "Invalid argument %s" % (args.type[0])
