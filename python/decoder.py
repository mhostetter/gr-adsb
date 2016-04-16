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

import numpy
from gnuradio import gr
import pmt
import csv

NUM_BITS            = 112 
NUM_BITS_TO_FLIP    = 1
CALLSIGN_LUT        = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ#####_###############0123456789######"

class decoder(gr.sync_block):
    """
    docstring for block decoder
    """
    def __init__(self, fs, error_corr, print_level):
        gr.sync_block.__init__(self,
            name="ADS-B Decoder",
            in_sig=[numpy.float32],
            out_sig=[numpy.float32])

        # Calculate the samples/symbol
        # ADS-B is modulated at 1 Msym/s with Pulse Position Modulation, so the effective
        # required fs is 2 Msps
        self.sps = fs/(1e6) 
        if (self.sps - numpy.floor(self.sps)) > 0:
            print "Warning: ADS-B Decoder is designed to operate on an integer number of samples per symbol"
        self.sps = int(self.sps) # Set the samples/symbol to an integer

        self.error_corr = error_corr
        self.print_level = print_level

        self.msg_count = 0
        self.snr = 0

        # Array of data bits
        self.bits = []
        self.bit_idx = 0
        self.straddled_packet = 0

        self.reset()

        # Propagate tags
        self.set_tag_propagation_policy(gr.TPP_ONE_TO_ONE)

        # Open files
        self.fp_csv = open("/home/matt/adsb.csv", "a")
        self.wr_csv = csv.writer(self.fp_csv)
        self.wr_csv.writerow(("DF", "CA", "AA", "TC", "PI"))

        # self.fp_db = open("/home/matt/adsb.sqlite", "w")

        print "Initialized ADS-B Decoder:"
        print "\tfs = %f Msym/s" % (fs/1e6)
        print "\tsps = %d" % (self.sps)


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

                self.bits = numpy.zeros(NUM_BITS, dtype=int)
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

        if self.print_level == "Verbose":
            print "\n\n"
            print "SNR\t%1.2f dB" % (self.snr)
            print "DF\t%d" % (self.df)
            print "CA\t%d" % (self.ca)
            print "AA\t%06x" % (self.aa)

        return


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

            if self.print_level == "Verbose":
                print "pi\t", self.pi
                print "crc\t", crc
                print "delta\t", self.pi - crc

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
        data = numpy.append(data, numpy.zeros(num_crc_bits, dtype=int))

        # CRC polynomial (0xFFFA048) = 1 + x + x^2 + x^3 + x^4 + x^5 + x^6 + x^7 + x^8 + x^9 + x^10 + x^11 + x^12 + x^14 + x^21 + x^24
        poly = numpy.array([1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,0,0,0,0,0,0,1,0,0,1])
        
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
            for ii in range(0,pow(2,NUM_BITS_TO_FLIP)):
                # Flip bit
                crc = self.compute_crc(112)
                if self.pi == crc:
                    return 1 # Parity passed
        
        elif self.error_corr == "Brute Force":
            # Implement this
            return 0 # Parity failed

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

                if self.print_level == "Verbose":
                    print "Callsign\t%s" % (self.callsign)

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
                alt = self.bits[40:40+12]

                # Time, 1 bit
                time = self.bits[52]

                # CPR Odd/Even Frame Flag, 1 bit
                odd_frame = self.bits[53]

                # Latitude in CPR Format, 17 bits
                lat_cpr = self.bin2dec(self.bits[54:54+17])

                # Longitude in CPR Format, 17 bits
                lon_cpr = self.bin2dec(self.bits[71:71+17])

                (lat_dec, lon_dec) = self.calculate_lat_lon()
                alt_ft = self.calculate_altitude()

                if self.print_level == "Verbose":
                    print "Airborne Position"
                    print "Latitude\t%d" % (lat_dec)
                    print "Longitude\t%d" % (lon_dec)
                    print "Altitude\t%d ft" % (alt_ft)

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
                    speed = numpy.sqrt(velocity_sn**2 + velocity_we**2)
                    
                    # Heading (degrees)
                    heading = numpy.arctan2(velocity_sn,velocity_we)*360.0/(2.0*numpy.pi)
                    
                    # Vertical Rate (ft/min)
                    vertical_rate = (vr - 1)*64
                    # s_vr = 0, ascending
                    # s_vr = 1, descending
                    if s_vr == 1:   
                        vertical_rate *= -1
                    
                    if self.print_level == "Verbose":
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
            self.tc = -1
            print self.df

        elif self.df == 19 and self.ca == 0:
            self.tc = -1
            print self.df

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

        # Write to a CSV file
        self.wr_csv.writerow((self.df, self.ca, self.aa, self.tc, self.pi))

        return


    # http://www.eurocontrol.int/eec/gallery/content/public/document/eec/report/1995/002_Aircraft_Position_Report_using_DGPS_Mode-S.pdf
    def calculate_lat_lon(self):
        lat_dec = 0
        lon_dec = 0
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
        alt_bits = numpy.delete(alt_bits, 7)
        alt_dec = self.bin2dec(alt_bits)

        # Altitude in ft
        alt_ft = alt_dec*multiplier - 1000

        return alt_ft

