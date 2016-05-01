# gr-adsb
A GNU Radio Out-Of-Tree (OOT) Module to demodulate and decode Automatic Dependent Surveillance Broadcast (ADS-B) messages.


## Features
* Supports many SDRs through GNU Radio and OsmoSDR (USRP, RTL-SDR, HackRF, BladeRF, etc).
* Supports various sample rates (2 Msps, 4 Msps, 6 Msps, etc).  Currently the sampling rate needs to be an integer multiple of 2*fsym or 2 Msps.
* Decoding of messages:
  * DF 0:  Short Air-Air Surveillance (ACAS)
  * DF 4:  Surveillance Altitude Reply
  * DF 5:  Surveillance Identity Reply
  * DF 11: All-Call Reply
  * DF 16: Long Air-Air Surveillance (ACAS)
  * DF 17: ADS-B Extended Squitter
  * DF 18: CF=0,1,6 ADS-B Extended Squitter from Non-Mode S Transponders
  * DF 19: AF=0 Military ADS-B Extended Squitter
  * DF 20: Comm-B Altitude Reply
* "Brief" stdout printing.
* "Verbose" stdout printing.
* Logging to a CSV file.
* Logging to a SQLite database.
* Script to generate Google Earth KML files from a SQLite database.


## Usage
### GNU Radio
There is an example GNU Radio Companion (.grc) file located at `/gr-adsb/examples/adsb_rx.grc`.  To use it, first open GNU Radio Companion `$ gnuradio-companion` and then open the .grc file.

![GRC Example Flowgraph](https://github.com/mhostetter/gr-adsb/blob/master/docs/adsb_rx.png)

Example "Brief" output:
```
 ICAO  Callsign  Alt  Climb Speed Hdng  Latitude    Longitude  Msgs Age
                 (ft) (ft/m) (kn) (deg)                             (s)
------ -------- ----- ----- ----- ---- ----------- ----------- ---- ---
a4da13 4349 60  16450  2240   360    9  39.0509491 -77.0292066   47  47
a72bda          27225                                           459   0
abe82c SWA3329  37000     0   481   39                            6 221
a00ca4 FDX1273  36025     0   407 -157  39.6801034 -77.9697876  273   0
a58a1b           1775                                             2   2
a1c534          24975 -2816   471   31                            9 233
a3cd6b          10575                                           542   0
a022ee FDX1234  28075  4352   455 -168  38.7769900 -78.8369141  168  23
a2dffe UAL1704   9725     0   307  -34  39.1294556 -78.0681909  114   0
aa8af7          16800     0   431   34  39.2041533 -76.5144043   59 110
a318ea          12075                                            27 257
aaf111 DAL1436  10525 -1152   303   -3  39.4307230 -76.9674072  921  55
ace5b6          16100                                             3   4
a50e47          29600                                           427  13
c00ec2          36975     0   413  103  37.9071614 -77.9345040  176   0
a8f63b FDX1679  25700  2240   419  175  38.9744110 -78.4300829  455  39
a8d62a FDX1630  34000     0   379  175  38.9746508 -78.4457397  126 234
```
Example "Verbose" Output:
```
----------------------------------------------------------------------
SNR:            18.50 dB
DF:             0 Short Air-Air Surveillance (ACAS)
Parity:         Passed (Recognized AA from AP)
AA:             a50e47
Units:          Standard
Altitude:       28800 ft

----------------------------------------------------------------------
SNR:            22.36 dB
DF:             4 Surveillance Altitude Reply
Parity:         Passed (Recognized AA from AP)
AA:             a50e47
FS:             0 No Alert, No SPI, In Air
DR:             0 No Downlink Request
IIS:            0
IDS:            0 No Information
Units:          Standard
Altitude:       28800 ft

----------------------------------------------------------------------
SNR:            8.76 dB
DF:             11 All-Call Reply
Parity:         Passed
CA:             5 Level >=2 Transponder, Can Set CA 7, In Air
AA:             a72bda

----------------------------------------------------------------------
SNR:            12.92 dB
DF:             17 Extended Squitter
Parity:         Passed
CA:             5 Level >=2 Transponder, Can Set CA 7, In Air
AA:             a8f63b
TC:             19 Airborne Velocity
Speed:          367 kn
Heading:        177 deg (W)
Climb:          3136 ft/min
Source:         Barometric Pressure Altitude Change Rate

----------------------------------------------------------------------
SNR:            16.79 dB
DF:             17 Extended Squitter
Parity:         Passed
CA:             5 Level >=2 Transponder, Can Set CA 7, In Air
AA:             aaf111
TC:             11 Airborne Position
Latitude:       39.4474182 N
Longitude:      -77.4949314 E
Altitude:       10775 ft
```

### KML Generation
Add image here.

## Installation
GNU Radio is a dependency for gr-adsb.  I recommend installing GNU Radio through PyBOMBS, see https://github.com/gnuradio/pybombs.

To build gr-adsb, follow this procedure.

1. `$ cd gr-adsb`
2. `$ mkdir build`
3. `$ cd build`
4. `$ cmake ../` or `$ cmake -DCMAKE_INSTALL_PREFIX=<path_to_install> ../`
5. `$ make`
6. `$ sudo make install`
7. `$ sudo ldconfig`

