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

from gnuradio import gr
import pmt
import numpy as np
import datetime as dt
import csv

NUM_BITS                = 112
NUM_PLANES_TO_TRACK     = 50
CPR_TIMEOUT_S           = 30 # Seconds consider CPR-encoded lat/lon info invalid
PLANE_TIMEOUT_S         = 5*60
CALLSIGN_LUT            = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"

class decoder(gr.sync_block):
    """
    docstring for block decoder
    """
    def __init__(self, fs, error_corr, print_level, log_csv, csv_filename, log_db, db_filename):
        gr.sync_block.__init__(self,
            name="ADS-B Decoder",
            in_sig=[np.float32],
            out_sig=[np.float32])

        # Calculate the samples/symbol
        # ADS-B is modulated at 1 Msym/s with Pulse Position Modulation, so the effective
        # required fs is 2 Msps
        self.sps = fs/(1e6) 
        if (self.sps - np.floor(self.sps)) > 0:
            print "Warning: ADS-B Decoder is designed to operate on an integer number of samples per symbol"
        self.sps = int(self.sps) # Set the samples/symbol to an integer

        self.error_corr = error_corr
        self.print_level = print_level
        self.log_csv = log_csv
        self.csv_filename = csv_filename
        self.log_db = log_db
        self.db_filename = db_filename

        # Array of data bits
        self.bits = []
        self.bit_idx = 0
        self.straddled_packet = 0

        # Initialize plane dictionary
        self.planes = dict([])

        # Reset packet values
        self.reset()

        # Propagate tags
        self.set_tag_propagation_policy(gr.TPP_ONE_TO_ONE)

        # Initialize CSV file
        if self.log_csv == True:
            self.fp_csv = open(self.csv_filename, "a")
            self.wr_csv = csv.writer(self.fp_csv)
            self.wr_csv.writerow(("Aircraft ID", "Callsign", "Altitude (ft)", "Speed (kn)", "Heading (deg", "Latitude", "Longitude", "Message Count", "Time Since Seen (s)"))

        # Initialize database
        if self.log_db == True:
            print "TODO: Needs to be implemented"
            # self.fp_db = open("/home/matt/adsb.sqlite", "w")

        print "\nInitialized ADS-B Decoder:"
        print "  Sampling Rate:       %1.2f Msps" % (fs/1e6)
        print "  Samples Per Symbol:  %d" % (self.sps)
        print "  Print Level:         %s" % (self.print_level)
        print "  Log to CSV:          %s" % (self.log_csv)
        if self.log_csv == True:
            print "    CSV Filename:      %s" % (self.csv_filename)
        print "  Log to Database:     %s" % (self.log_db)
        if self.log_db == True:
            print "    Database Filename: %s" % (self.db_filename)
            

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out0 = output_items[0]

        # If there was a packet that straddled the previous block and this
        # block, finish decoding it
        if self.straddled_packet == 1:
            self.straddled_packet = 0

        # Get tags from ADS-B Framer block
        tags = self.get_tags_in_window(0, 0, len(in0), pmt.to_pmt("burst"))

        bit1_idxs = []
        bit0_idxs = []

        for tag in tags:
            # Grab metadata for this tag
            value = pmt.to_python(tag.value)
            self.snr = value[1] # SNR in power dBs

            # Calculate the SOB and EOB offsets            
            sob_offset = tag.offset + (8)*self.sps # Start of burst index (middle of the "bit 1 pulse")
            eob_offset = tag.offset + (8+112-1)*self.sps + self.sps/2 # End of burst index (middle of the "bit 0 pulse")

            # Find the SOB and EOB indices in this block of samples
            sob_idx = sob_offset - self.nitems_written(0)
            eob_idx = eob_offset - self.nitems_written(0)

            if eob_idx < len(input_items[0]):
                # The packet is fully within this block of samples, so demod
                # the entire burst

                # Grab the amplitudes where the "bit 1 pulse" should be
                bit1_idxs = range(sob_idx, sob_idx+self.sps*NUM_BITS, self.sps)
                bit1_amps = in0[bit1_idxs]

                # Grab the amplitudes where the "bit 0 pulse" should be
                bit0_idxs = range(sob_idx+self.sps/2, sob_idx+self.sps*NUM_BITS+self.sps/2, self.sps)
                bit0_amps = in0[bit0_idxs]

                self.bits = np.zeros(NUM_BITS, dtype=int)
                self.bits[bit1_amps > bit0_amps] = 1

                # Reset decoder values before decoding next burs
                self.reset()

                # Decode the header (common) part of the packet
                self.decode_header()

                if self.check_parity() == 1:
                    # If parity check passes, then decode the message contents
                    self.decode_message()

            else:
                # The packet is only partially contained in this block of
                # samples, decode as much as possible
                self.straddled_packet = 1
                # print "Straddled packet"


            if 0:
                # Tag the 0 and 1 bits markers for debug
                for ii in range(0,len(bit1_idxs)):
                    self.add_item_tag(  0,
                                        self.nitems_written(0)+bit1_idxs[ii],
                                        pmt.to_pmt("bits"),
                                        pmt.to_pmt("1"),    
                                        pmt.to_pmt("decoder")
                                    )
                    self.add_item_tag(  0, 
                                        self.nitems_written(0)+bit0_idxs[ii], 
                                        pmt.to_pmt("bits"),
                                        pmt.to_pmt("0"), 
                                        pmt.to_pmt("decoder")
                                    )


        out0[:] = in0
        return len(output_items[0])


    def reset(self):
        self.df = 0
        self.ca = 0
        self.aa = 0
        self.me = 0
        self.pi = 0
        self.tc = 0
        self.callsign = ""


    def bin2dec(self, bits):
        return int("".join(map(str,bits)),2)


    def update_plane(self, aa_str):
        if self.planes.has_key(aa_str) == True:
            seconds_since_last_seen = (dt.datetime.now() - self.planes[aa_str]["last_seen"]).total_seconds()
            if seconds_since_last_seen > PLANE_TIMEOUT_S:
                # If the plane has timed out, delete its old altimetry values
                self.reset_plane_altimetry(self.planes[aa_str])

            self.planes[aa_str]["num_msgs"] += 1
            self.planes[aa_str]["last_seen"] = dt.datetime.now()
            
        else:
            # Create empty dictionary for this plane
            self.planes[aa_str] = dict([])
            self.planes[aa_str]["callsign"] = ""
            self.reset_plane_altimetry(self.planes[aa_str])

            self.planes[aa_str]["num_msgs"] = 1
            self.planes[aa_str]["last_seen"] = dt.datetime.now()

            if len(self.planes) > NUM_PLANES_TO_TRACK:
                # Delete oldest plane from dictionary
                #
                # Implement this
                #
                a = 1        

        # print "Planes Dictionary ***********************"
        # print self.planes
        # for plane in self.planes:
        #     print plane


    def reset_plane_altimetry(self, plane):
        plane["alt"] = np.NaN
        plane["speed"] = np.NaN
        plane["heading"] = np.NaN
        plane["lat"] = np.NaN
        plane["lon"] = np.NaN
        # plane["cpr"] = np.ndarray((2,3))
        plane["cpr"] = [(np.NaN, np.NaN, dt.datetime.fromtimestamp(0)),(np.NaN, np.NaN, dt.datetime.fromtimestamp(0))]


    def print_planes(self):
        print "\n\n"
        print "Aircarft Callsign Alt   Speed Hdng Lat         Lon         Msgs Secs"
        print "-------- -------- ----- ----- ---- ----------- ----------- ---- ----"
        # print "a6234b   ABC123__ 38000 375   -176 75.4444     34.898      71   10  "

        for key in self.planes.keys():
            print "%s   %s %s %s %s %s %s %s %s" % (key,
                    "{:8s}".format(self.planes[key]["callsign"]),
                    "{:5.0f}".format(self.planes[key]["alt"]),
                    "{:5.0f}".format(self.planes[key]["speed"]),
                    "{:4.0f}".format(self.planes[key]["heading"]),
                    "{:11.7f}".format(self.planes[key]["lat"]),
                    "{:11.7f}".format(self.planes[key]["lon"]),
                    "{:4d}".format(self.planes[key]["num_msgs"]),
                    "{:4.0f}".format((dt.datetime.now() - self.planes[key]["last_seen"]).total_seconds())
                )


    def write_plane_to_csv(self):
        # Write current plane to CSV file
        self.wr_csv.writerow((self.aa_str,
                    "{:8s}".format(self.planes[self.aa_str]["callsign"]),
                    "{:5.0f}".format(self.planes[self.aa_str]["alt"]),
                    "{:5.0f}".format(self.planes[self.aa_str]["speed"]),
                    "{:4.0f}".format(self.planes[self.aa_str]["heading"]),
                    "{:11.7f}".format(self.planes[self.aa_str]["lat"]),
                    "{:11.7f}".format(self.planes[self.aa_str]["lon"]),
                    "{:4d}".format(self.planes[self.aa_str]["num_msgs"]),
                    "{:4.0f}".format((dt.datetime.now() - self.planes[self.aa_str]["last_seen"]).total_seconds()))
                )


    def write_plane_to_db(self):
        # Write current plane to database
        print "TODO: Need to implement this"
        # self.wr_csv.writerow((self.aa_str,
        #             "{:8s}".format(self.planes[self.aa_str]["callsign"]),
        #             "{:5.0f}".format(self.planes[self.aa_str]["alt"]),
        #             "{:5.0f}".format(self.planes[self.aa_str]["speed"]),
        #             "{:4.0f}".format(self.planes[self.aa_str]["heading"]),
        #             "{:11.7f}".format(self.planes[self.aa_str]["lat"]),
        #             "{:11.7f}".format(self.planes[self.aa_str]["lon"]),
        #             "{:4d}".format(self.planes[self.aa_str]["num_msgs"]),
        #             "{:4.0f}".format((dt.datetime.now() - self.planes[self.aa_str]["last_seen"]).total_seconds()))
        #         )


    # http://www.bucharestairports.ro/files/pages_files/Vol_IV_-_4yh_ed,_July_2007.pdf
    # http://www.icao.int/APAC/Documents/edocs/cns/SSR_%20modesii.pdf
    # http://www.anteni.net/adsb/Doc/1090-WP30-18-DRAFT_DO-260B-V42.pdf
    # http://www.cats.com.kh/download.php?path=vdzw4dHS08mjtKi6vNi31Mbn0tnZ2eycn6ydmqPE19rT7Mze4cSYpsetmdXd0w==
    def decode_header(self):
        # See http://www.sigidwiki.com/images/1/15/ADS-B_for_Dummies.pdf

        # Downlink Format, 5 bits
        self.df = self.bin2dec(self.bits[0:0+5])

        # Capability, 3 bits
        self.ca = self.bin2dec(self.bits[5:5+3])
        
        # Address Announced (ICAO Address) 24 bits
        self.aa = self.bin2dec(self.bits[8:8+24])
        self.aa_str = "%06x" % (self.aa)

        if self.print_level == "Verbose":
            if self.df == 17:
                print "\n\n"
                print "SNR\t%1.2f dB" % (self.snr)
                print "DF\t%d" % (self.df)
                print "CA\t%d" % (self.ca)
                print "AA\t%s" % (self.aa_str)


    # http://jetvision.de/sbs/adsb/crc.htm
    def check_parity(self):
        # if self.df in [0,4,5,11]:
        #     # 56 bit payload

        #     # Parity/Interrogator ID, 24 bits
        #     self.pi = self.bin2dec(self.bits[32:32+24])

        #     print "pi bits"
        #     print self.bits[32:32+24]

        #     crc = self.compute_crc(56)

        if self.df in [16,17,18,19,20,21]:
            # 112 bit payload

            # Parity/Interrogator ID, 24 bits
            self.pi = self.bin2dec(self.bits[88:88+24])

            crc = self.compute_crc(112)

            # if self.print_level == "Verbose":
                # print "pi\t", self.pi
                # print "crc\t", crc
                # print "delta\t", self.pi - crc

            if self.pi == crc:
                return 1 # Parity passed
            else:
                return self.correct_errors()

        else:
            # Unsupported downlink format
            return 0 # Parity failed


    # http://www.radarspotters.eu/forum/index.php?topic=5617.msg41293#msg41293
    # http://www.eurocontrol.int/eec/gallery/content/public/document/eec/report/1994/022_CRC_calculations_for_Mode_S.pdf
    def compute_crc(self, payload_length):
        num_crc_bits = 24 # For all payload lengths
        num_data_bits = payload_length - num_crc_bits

        data = self.bits[0:num_data_bits]
        data = np.append(data, np.zeros(num_crc_bits, dtype=int))

        # CRC polynomial (0xFFFA048) = 1 + x + x^2 + x^3 + x^4 + x^5 + x^6 + x^7 + x^8 + x^9 + x^10 + x^11 + x^12 + x^14 + x^21 + x^24
        poly = np.array([1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,0,0,0,0,0,0,1,0,0,1])
        
        for ii in range(0,num_data_bits):
            if data[ii] == 1:
                # XOR the data with the CRC polynomial
                # NOTE: The data polynomial and CRC polynomial are Galois Fields
                # in GF(2)
                data[ii:ii+num_crc_bits+1] = (data[ii:ii+num_crc_bits+1] + poly) % 2

        # print "crc bits"
        # print data[num_data_bits:num_data_bits+num_crc_bits]

        crc = self.bin2dec(data[num_data_bits:num_data_bits+num_crc_bits])

        return crc


    def correct_errors(self):
        if self.error_corr == "None":
            return 0 # Didn't attempt to make the parity pass

        if self.error_corr == "Conservative":
            for ii in range(0,pow(2,2)):
                # Flip bit
                crc = self.compute_crc(112)
                if self.pi == crc:
                    return 1 # Parity passed
        
        elif self.error_corr == "Brute Force":
            for ii in range(0,pow(2,5)):
                # Flip bit
                crc = self.compute_crc(112)
                if self.pi == crc:
                    return 1 # Parity passed

        else:
            return 0 # Parity failed
        

    # http://adsb-decode-guide.readthedocs.org/en/latest/introduction.html
    def decode_message(self):
        if self.df == 17:
            # Type Code, 5 bits
            self.tc = self.bin2dec(self.bits[32:32+5])
            
            if self.print_level == "Verbose":
                print "TC\t%d" % (self.tc)

            ### Aircraft Indentification ###
            if self.tc in range(1,5):
                # Grab callsign using character LUT
                self.callsign = ""
                
                for ii in range(0,8):
                    # There are 8 characters in the callsign, each is represented using
                    # 6 bits
                    self.callsign += CALLSIGN_LUT[self.bin2dec(self.bits[40+ii*6:40+(ii+1)*6])]

                # Update planes dictionary
                self.update_plane(self.aa_str)
                self.planes[self.aa_str]["callsign"] = self.callsign

                if self.print_level == "Brief":
                    self.print_planes()
                elif self.print_level == "Verbose":
                    print "Callsign\t%s" % (self.callsign)

                if self.log_csv == True:
                    self.write_plane_to_csv()

                if self.log_db == True:
                    self.write_plane_to_db()

            ### Surface Position ###
            elif self.tc in range(5,9):
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)
            
            ### Airborne Position (Baro Altitude) ###
            elif self.tc in range(9,19):
                # Surveillance Status, 2 bits
                ss = self.bin2dec(self.bits[37:37+2])

                # NIC Supplement-B, 1 bit
                nic_sb = self.bits[39]

                # Altitude, 12 bits
                alt_bits = self.bits[40:40+12]

                # Time, 1 bit
                time = self.bits[52]

                # CPR Odd/Even Frame Flag, 1 bit
                frame = self.bits[53]

                # Latitude in CPR Format, 17 bits
                lat_cpr = self.bin2dec(self.bits[54:54+17])

                # Longitude in CPR Format, 17 bits
                lon_cpr = self.bin2dec(self.bits[71:71+17])

                # Update planes dictionary
                self.update_plane(self.aa_str)
                self.planes[self.aa_str]["cpr"][frame] = (lat_cpr, lon_cpr, dt.datetime.now())

                (lat_dec, lon_dec) = self.calculate_lat_lon(self.planes[self.aa_str]["cpr"])
                alt = self.calculate_altitude()

                if lat_dec != np.NaN and lon_dec != np.NaN:
                    self.planes[self.aa_str]["alt"] = alt
                    self.planes[self.aa_str]["lat"] = lat_dec
                    self.planes[self.aa_str]["lon"] = lon_dec

                if self.print_level == "Brief":
                    self.print_planes()
                elif self.print_level == "Verbose":
                    print "Airborne Position"
                    print "Altitude\t%d ft" % (alt)
                    print "Latitude\t%d" % (lat_dec)
                    print "Longitude\t%d" % (lon_dec)

                if self.log_csv == True:
                    self.write_plane_to_csv()

                if self.log_db == True:
                    self.write_plane_to_db()

            ### Airborne Velocities ###
            elif self.tc in [19]:
                # Sub Type, 3 bits
                st = self.bin2dec(self.bits[37:37+3])

                # Ground velocity subtype
                if st in [1,2]:
                    # Intent Change Flag, 1 bit
                    ic = self.bits[40]

                    # Reserved-A, 1 bit
                    resv_a = self.bits[41]

                    # Velocity Uncertainty (NAC), 3 bits
                    nac = self.bin2dec(self.bits[42:42+3])

                    # Velocity Sign East-West, 1 bit
                    nac = self.bits[45]

                    # Velocity Sign East-West, 1 bit
                    s_ew = self.bits[45]

                    # Velocity East-West, 10 bits
                    v_ew = self.bin2dec(self.bits[46:46+10])

                    # Velocity Sign North-South, 1 bit
                    s_ns = self.bits[56]

                    # Velocity North-South, 10 bits
                    v_ns = self.bin2dec(self.bits[57:57+10])

                    # Vertical Rate Source, 1 bit
                    vr_src = self.bits[67]

                    # Vertical Rate Sign, 1 bit
                    s_vr = self.bits[68]

                    # Vertical Rate, 9 bits
                    vr = self.bin2dec(self.bits[69:69+9])
                    
                    # Reserved-B, 2 bits
                    resv_b = self.bin2dec(self.bits[78:78+2])

                    # Difference from Baro Altitude and GNSS Height (HAE) Sign, 1 bit
                    s_diff = self.bits[80]

                    # Difference from Baro Altitude and GNSS Height (HAE), 7 bits
                    diff = self.bits[81:81+7]

                    # Velocity West to East
                    velocity_we = (v_ew - 1)
                    # s_ew = 0, flying West ot East
                    # s_ew = 1, flying East to West
                    if s_ew == 1:
                        velocity_we *= -1 # Flip direction

                    # Velocity South to North
                    velocity_sn = (v_ns - 1)
                    # s_ns = 0, flying South to North
                    # s_ns = 1, flying North to South
                    if s_ns == 1:
                        velocity_sn *= -1 # Flip direction

                    # Speed (knots)
                    speed = np.sqrt(velocity_sn**2 + velocity_we**2)
                    
                    # Heading (degrees)
                    heading = np.arctan2(velocity_sn,velocity_we)*360.0/(2.0*np.pi)
                    
                    # Vertical Rate (ft/min)
                    vertical_rate = (vr - 1)*64
                    # s_vr = 0, ascending
                    # s_vr = 1, descending
                    if s_vr == 1:   
                        vertical_rate *= -1
                    
                    # Update planes dictionary
                    self.update_plane(self.aa_str)
                    self.planes[self.aa_str]["speed"] = speed
                    self.planes[self.aa_str]["heading"] = heading

                    if self.print_level == "Brief":
                        self.print_planes()
                    elif self.print_level == "Verbose":
                        print "Ground Velocity"
                        print "Velocity W-E\t%1.2f knots" % (velocity_we)
                        print "Velocity S-N\t%1.2f knots" % (velocity_sn)
                        print "Speed\t\t%1.2f knots" % (speed)
                        print "Heading\t\t%1.1f deg" % (heading)
                        print "Vertical Rate\t%d ft/min" % (vertical_rate)
                        if vr_src == 0:
                            print "Baro-pressure altitude change rate"
                        elif vr_src == 1:
                            print "Geometric altitude change rate"
                        else:
                            print "Unknown vertical rate source"
        
                    if self.log_csv == True:
                        self.write_plane_to_csv()

                    if self.log_db == True:
                        self.write_plane_to_db()

                # Airborne velocity subtype
                elif st in [3,4]:                
                    if self.print_level == "Verbose":
                        print "Air Velocity"

                else:
                    print "DF %d TC %d ST %d Not yet implemented" % (self.df, self.tc, self.st)

            ### Airborne Position (GNSS Height) ###
            elif self.tc in range(20,23):
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Test Message ###
            elif self.tc in [23]:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Surface System Status ###
            elif self.tc in [24]:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Reserved ###
            elif self.tc in range(25,28):
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Extended Squitter A/C Status ###
            elif self.tc in [28]:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Target State and Status (V.2) ###
            elif self.tc in [29]:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Reserved ###
            elif self.tc in [30]:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            ### Aircraft Operation Status ###
            elif self.tc in [31]:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

            else:
                print "DF %d TC %d Not yet implemented" % (self.df, self.tc)


        elif self.df == 18 and self.ca in [0,1,6]:
            # Type Code, 5 bits
            self.tc = self.bin2dec(self.bits[32:32+5])

            print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

        elif self.df == 19 and self.ca == 0:
            # Type Code, 5 bits
            self.tc = self.bin2dec(self.bits[32:32+5])

            print "DF %d TC %d Not yet implemented" % (self.df, self.tc)

        # if self.df == 11:
        #     print "Acq squitter"        
        # if self.df == 17:
        #     print = "ADS-B"
        # elif self.df == 18:
        #     print "TIS-B"
        # elif self.df == 19:
        #     print "Military"
        # elif self.df == 28:
        #     print "Emergency/priority status"
        # elif self.df == 31:
        #     print "Aircraft operational status"
        # else:
        #     print "Unknown DF"


    # http://www.eurocontrol.int/eec/gallery/content/public/document/eec/report/1995/002_Aircraft_Position_Report_using_DGPS_Mode-S.pdf
    def calculate_lat_lon(self, cpr):
        # If the even and odd frame data is still valid, calculatte the
        # latitude and longitude
        if (dt.datetime.now() - cpr[0][2]).total_seconds() < CPR_TIMEOUT_S and (dt.datetime.now() - cpr[1][2]).total_seconds() < CPR_TIMEOUT_S:
            # Get fractional lat/lon for the even and odd frame
            # Even frame
            lat_cpr_even = float(cpr[0][0])/131072
            lon_cpr_even = float(cpr[0][1])/131072

            # Odd frame
            lat_cpr_odd = float(cpr[1][0])/131072
            lon_cpr_odd = float(cpr[1][1])/131072

            # Calculate the latitude index
            j = int(np.floor(59*lat_cpr_even - 60*lat_cpr_odd + 0.5))

            lat_even = 360.0/60*((j % 60) + lat_cpr_even)
            if lat_even >= 270:
                lat_even -= 360

            lat_odd = 360.0/59*((j % 59) + lat_cpr_odd)
            if lat_odd >= 270:
                lat_odd -= 360

            nl_even_old = self.compute_cpr_nl(lat_even)
            nl_odd_old = self.compute_cpr_nl(lat_odd)

            nl_even = self.cpr_nl(lat_even)
            nl_odd = self.cpr_nl(lat_odd)

            if nl_even == nl_odd:
                # Even/odd latitudes are in the same latitude zone, use the
                # most recent latitude
                if (cpr[0][2] - cpr[1][2]).total_seconds() > 0:
                    # The even frame is more recent
                    lat_dec = lat_even

                    # Calculate longitude
                    ni = self.cpr_n(lat_even, 0)
                    m = int(np.floor(lon_cpr_even*(self.cpr_nl(lat_even)-1) - lon_cpr_odd*self.cpr_nl(lat_even) + 0.5))
                    lon_dec = (360.0/ni)*((m % ni) + lon_cpr_even)
                    if lon_dec >= 180.0:
                        lon_dec -= 360.0

                else:
                    # The odd frame is more recent
                    lat_dec = lat_odd

                    # Calculate longitude
                    ni = self.cpr_n(lat_odd, 1)
                    m = int(np.floor(lon_cpr_even*(self.cpr_nl(lat_odd)-1) - lon_cpr_odd*self.cpr_nl(lat_odd) + 0.5))
                    lon_dec = (360.0/ni)*((m % ni) + lon_cpr_odd)
                    if lon_dec >= 180.0:
                        lon_dec -= 360.0

            else:
                # Even/odd latitudes are not in the same latitude zones, wait
                # for more data
                lat_dec = np.NaN
                lon_dec = np.NaN

        else:
            lat_dec = np.NaN
            lon_dec = np.NaN

        return (lat_dec, lon_dec)


    # http://www.eurocontrol.int/eec/gallery/content/public/document/eec/report/1995/002_Aircraft_Position_Report_using_DGPS_Mode-S.pdf
    def calculate_altitude(self):
        # Altitude, 12 bits
        alt_bits = self.bits[40:40+12]

        # Q-bit, 1 bit
        q_bit = self.bits[47]

        if q_bit == 0:
            # Q-bit = 0, altitude is encoded in multiples of 100 ft
            multiplier = 100
        else:
            # Q-bit = 1, altitude is encoded in multiples of 25 ft
            multiplier = 25

        # Remove the Q-bit from the altitude bits to calculate the
        # altitude
        alt_bits = np.delete(alt_bits, 7)
        alt_dec = self.bin2dec(alt_bits)

        # Altitude in ft
        alt = alt_dec*multiplier - 1000

        return alt



    def cpr_n(self, lat, frame):
        # frame = 0, even frame
        # frame = 1, odd frame
        n = self.cpr_nl(lat) - frame;

        if n > 1:
            return n
        else:
            return 1


    def compute_cpr_nl(self, lat):
        NZ = 60.0
        # TODO: Might need to tweak this equation
        return int(2.0*np.pi/(np.arccos(1.0 - (1.0-np.cos(np.pi/(2.0*NZ)))/(np.cos(2.0*np.pi*abs(lat)/180.0)**2))))


    def cpr_nl(self, lat):
        if lat < 0:
            lat = -lat
        
        if lat < 10.47047130:
            return 59
        elif lat < 14.82817437:
            return 58
        elif lat < 18.18626357:
            return 57
        elif lat < 21.02939493:
            return 56
        elif lat < 23.54504487:
            return 55
        elif lat < 25.82924707:
            return 54
        elif lat < 27.93898710:
            return 53
        elif lat < 29.91135686:
            return 52
        elif lat < 31.77209708:
            return 51
        elif lat < 33.53993436:
            return 50
        elif lat < 35.22899598:
            return 49
        elif lat < 36.85025108:
            return 48
        elif lat < 38.41241892:
            return 47
        elif lat < 39.92256684:
            return 46
        elif lat < 41.38651832:
            return 45
        elif lat < 42.80914012:
            return 44
        elif lat < 44.19454951:
            return 43
        elif lat < 45.54626723:
            return 42
        elif lat < 46.86733252:
            return 41
        elif lat < 48.16039128:
            return 40
        elif lat < 49.42776439:
            return 39
        elif lat < 50.67150166:
            return 38
        elif lat < 51.89342469:
            return 37
        elif lat < 53.09516153:
            return 36
        elif lat < 54.27817472:
            return 35
        elif lat < 55.44378444:
            return 34
        elif lat < 56.59318756:
            return 33
        elif lat < 57.72747354:
            return 32
        elif lat < 58.84763776:
            return 31
        elif lat < 59.95459277:
            return 30
        elif lat < 61.04917774:
            return 29
        elif lat < 62.13216659:
            return 28
        elif lat < 63.20427479:
            return 27
        elif lat < 64.26616523:
            return 26
        elif lat < 65.31845310:
            return 25
        elif lat < 66.36171008:
            return 24
        elif lat < 67.39646774:
            return 23
        elif lat < 68.42322022:
            return 22
        elif lat < 69.44242631:
            return 21
        elif lat < 70.45451075:
            return 20
        elif lat < 71.45986473:
            return 19
        elif lat < 72.45884545:
            return 18
        elif lat < 73.45177442:
            return 17
        elif lat < 74.43893416:
            return 16
        elif lat < 75.42056257:
            return 15
        elif lat < 76.39684391:
            return 14
        elif lat < 77.36789461:
            return 13
        elif lat < 78.33374083:
            return 12
        elif lat < 79.29428225:
            return 11
        elif lat < 80.24923213:
            return 10
        elif lat < 81.19801349:
            return 9
        elif lat < 82.13956981:
            return 8
        elif lat < 83.07199445:
            return 7
        elif lat < 83.99173563:
            return 6
        elif lat < 84.89166191:
            return 5
        elif lat < 85.75541621:
            return 4
        elif lat < 86.53536998:
            return 3
        elif lat < 87.00000000:
            return 2
        else:
            return 1