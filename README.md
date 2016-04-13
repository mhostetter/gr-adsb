# gr-adsb

A GNU Radio Out-Of-Tree (OOT) Module to demodulate and decode Automatic Dependent Surveillance Broadcast (ADS-B) messages.

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

