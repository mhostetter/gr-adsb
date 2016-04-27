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
* Refreshing brief stdout printing.
* Verbose stdout printing.
* Logging to a CSV file.
* Logging to a SQLite database.
* Script to generate Google Earth KML files from a SQLite database.


## Usage

There is an example GNU Radio flowgraph located in `/examples/adsb_rx.grc`  You can open the flowgraph through GNU Radio Companion `$ gnuradio-companion`.


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

