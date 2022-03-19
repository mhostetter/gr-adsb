#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: ADS-B Receiver
# Author: Matt Hostetter
# GNU Radio version: v3.11.0.0git-55-g8526e6f8

from packaging.version import Version as StrictVersion

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print("Warning: failed to XInitThreads()")

from PyQt5 import Qt
from gnuradio import eng_notation
from gnuradio import qtgui
from gnuradio.filter import firdes
import sip
from gnuradio import analog
from gnuradio import blocks
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import uhd
import time
from gnuradio import zeromq
import gnuradio.adsb as adsb



from gnuradio import qtgui

class adsb_rx(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "ADS-B Receiver", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("ADS-B Receiver")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
            pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "adsb_rx")

        try:
            if StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
                self.restoreGeometry(self.settings.value("geometry").toByteArray())
            else:
                self.restoreGeometry(self.settings.value("geometry"))
        except:
            pass

        ##################################################
        # Variables
        ##################################################
        self.threshold = threshold = 0.010
        self.gain = gain = 100
        self.fs = fs = 2e6
        self.fc = fc = 1090e6

        ##################################################
        # Blocks
        ##################################################
        self._threshold_tool_bar = Qt.QToolBar(self)
        self._threshold_tool_bar.addWidget(Qt.QLabel("Detection Threshold" + ": "))
        self._threshold_line_edit = Qt.QLineEdit(str(self.threshold))
        self._threshold_tool_bar.addWidget(self._threshold_line_edit)
        self._threshold_line_edit.returnPressed.connect(
            lambda: self.set_threshold(eng_notation.str_to_num(str(self._threshold_line_edit.text()))))
        self.top_grid_layout.addWidget(self._threshold_tool_bar, 0, 1, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(1, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._gain_tool_bar = Qt.QToolBar(self)
        self._gain_tool_bar.addWidget(Qt.QLabel("Gain (dB)" + ": "))
        self._gain_line_edit = Qt.QLineEdit(str(self.gain))
        self._gain_tool_bar.addWidget(self._gain_line_edit)
        self._gain_line_edit.returnPressed.connect(
            lambda: self.set_gain(eng_notation.str_to_num(str(self._gain_line_edit.text()))))
        self.top_grid_layout.addWidget(self._gain_tool_bar, 0, 0, 1, 1)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 1):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.zeromq_pub_msg_sink_0 = zeromq.pub_msg_sink('tcp://127.0.0.1:5001', 10, True)
        self.uhd_usrp_source_0 = uhd.usrp_source(
            ",".join(("", "")),
            uhd.stream_args(
                cpu_format="fc32",
                args='',
                channels=list(range(0,1)),
            ),
        )
        self.uhd_usrp_source_0.set_samp_rate(fs)
        self.uhd_usrp_source_0.set_time_unknown_pps(uhd.time_spec(0))

        self.uhd_usrp_source_0.set_center_freq(fc, 0)
        self.uhd_usrp_source_0.set_antenna('TX/RX', 0)
        self.uhd_usrp_source_0.set_gain(gain, 0)
        self.qtgui_time_sink_x_0 = qtgui.time_sink_f(
            int(fs*150e-6), #size
            int(fs), #samp_rate
            "", #name
            2, #number of inputs
            None # parent
        )
        self.qtgui_time_sink_x_0.set_update_time(1.0/100.0)
        self.qtgui_time_sink_x_0.set_y_axis(0, 1)

        self.qtgui_time_sink_x_0.set_y_label('Amplitude', "")

        self.qtgui_time_sink_x_0.enable_tags(True)
        self.qtgui_time_sink_x_0.set_trigger_mode(qtgui.TRIG_MODE_TAG, qtgui.TRIG_SLOPE_POS, 0, 1.25e-6, 0, "burst")
        self.qtgui_time_sink_x_0.enable_autoscale(False)
        self.qtgui_time_sink_x_0.enable_grid(True)
        self.qtgui_time_sink_x_0.enable_axis_labels(True)
        self.qtgui_time_sink_x_0.enable_control_panel(False)
        self.qtgui_time_sink_x_0.enable_stem_plot(False)

        self.qtgui_time_sink_x_0.disable_legend()

        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [0, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                self.qtgui_time_sink_x_0.set_line_label(i, "Data {0}".format(i))
            else:
                self.qtgui_time_sink_x_0.set_line_label(i, labels[i])
            self.qtgui_time_sink_x_0.set_line_width(i, widths[i])
            self.qtgui_time_sink_x_0.set_line_color(i, colors[i])
            self.qtgui_time_sink_x_0.set_line_style(i, styles[i])
            self.qtgui_time_sink_x_0.set_line_marker(i, markers[i])
            self.qtgui_time_sink_x_0.set_line_alpha(i, alphas[i])

        self._qtgui_time_sink_x_0_win = sip.wrapinstance(self.qtgui_time_sink_x_0.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_time_sink_x_0_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.blocks_complex_to_mag_squared_0 = blocks.complex_to_mag_squared(1)
        self.analog_const_source_x_0 = analog.sig_source_f(0, analog.GR_CONST_WAVE, 0, 0, threshold)
        self.adsb_framer_1 = adsb.framer(fs, threshold)
        self.adsb_demod_0 = adsb.demod(fs)
        self.adsb_decoder_0 = adsb.decoder("Extended Squitter Only", "None", "Brief")


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.adsb_decoder_0, 'decoded'), (self.zeromq_pub_msg_sink_0, 'in'))
        self.msg_connect((self.adsb_demod_0, 'demodulated'), (self.adsb_decoder_0, 'demodulated'))
        self.connect((self.adsb_demod_0, 0), (self.qtgui_time_sink_x_0, 0))
        self.connect((self.adsb_framer_1, 0), (self.adsb_demod_0, 0))
        self.connect((self.analog_const_source_x_0, 0), (self.qtgui_time_sink_x_0, 1))
        self.connect((self.blocks_complex_to_mag_squared_0, 0), (self.adsb_framer_1, 0))
        self.connect((self.uhd_usrp_source_0, 0), (self.blocks_complex_to_mag_squared_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "adsb_rx")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_threshold(self):
        return self.threshold

    def set_threshold(self, threshold):
        self.threshold = threshold
        Qt.QMetaObject.invokeMethod(self._threshold_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.threshold)))
        self.adsb_framer_1.set_threshold(self.threshold)
        self.analog_const_source_x_0.set_offset(self.threshold)

    def get_gain(self):
        return self.gain

    def set_gain(self, gain):
        self.gain = gain
        Qt.QMetaObject.invokeMethod(self._gain_line_edit, "setText", Qt.Q_ARG("QString", eng_notation.num_to_str(self.gain)))
        self.uhd_usrp_source_0.set_gain(self.gain, 0)

    def get_fs(self):
        return self.fs

    def set_fs(self, fs):
        self.fs = fs
        self.qtgui_time_sink_x_0.set_samp_rate(int(self.fs))
        self.uhd_usrp_source_0.set_samp_rate(self.fs)

    def get_fc(self):
        return self.fc

    def set_fc(self, fc):
        self.fc = fc
        self.uhd_usrp_source_0.set_center_freq(self.fc, 0)




def main(top_block_cls=adsb_rx, options=None):

    if StrictVersion("4.5.0") <= StrictVersion(Qt.qVersion()) < StrictVersion("5.0.0"):
        style = gr.prefs().get_string('qtgui', 'style', 'raster')
        Qt.QApplication.setGraphicsSystem(style)
    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
