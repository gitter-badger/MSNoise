"""
This plot shows the cross-correlation functions (CCF) vs time. The parameters
allow to plot the daily or the mov-stacked CCF. Filters and components are
selectable too. The ``--ampli`` argument allows to increase the vertical scale
of the CCFs. The ``--seismic`` shows the up-going wiggles with a black-filled
background (very heavy !).

.. include:: clickhelp/msnoise-plot-ccftime.rst


Example:

``msnoise plot ccftime ID.KWUI ID.POSI`` will plot all defaults:

.. image:: .static/ccftime.png
"""
# plot interferogram
import matplotlib.pyplot as plt
from matplotlib.dates import date2num, DateFormatter, DayLocator, MonthLocator, YearLocator
from scipy.stats import scoreatpercentile
from scipy.stats.stats import nanmean

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
from matplotlib.widgets import Cursor

import os
import numpy as np
import sys
import scipy.signal
from obspy.core import read, Stream, Trace

from ..api import *


def main(sta1, sta2, filterid, components, mov_stack=1, ampli=5, seismic=False,
         show=False, outfile=None):
    db = connect()
    maxlag = float(get_config(db,'maxlag'))
    samples = get_maxlag_samples(db)
    cc_sampling_rate = float(get_config(db,'cc_sampling_rate'))
    start, end, datelist = build_movstack_datelist(db)
    base = mdates.date2num(start) 
    plt.figure(figsize=(16,16))
    sta1 = sta1.replace('.','_')
    sta2 = sta2.replace('.','_')
    t = np.arange(samples)/cc_sampling_rate - maxlag

    if sta2 > sta1: # alphabetical order filtering!
        pair = "%s:%s"%(sta1,sta2)
        
        print "New Data for %s-%s-%i-%i"%(pair,components,filterid, mov_stack)
        format = "matrix"
        nstack, stack_total = get_results(db,sta1,sta2,filterid,components,datelist,mov_stack, format=format)
        ax = plt.subplot(111)
        for i, line in enumerate(stack_total):
            line /= line.max()
            plt.plot(t, line * ampli + i + base , c='k')
            if seismic:
                y1 = np.ones(len(line)) * i
                y2 = line*ampli + i + base
                plt.fill_between(t, y1, y2, where=y2>=y1, facecolor='k', interpolate=True)

        plt.xlabel("Lag Time (s)")
        plt.axhline(0,lw=0.5,c='k')
        plt.grid()
        plt.title('%s : %s'%(sta1.replace('_', '.'), sta2.replace('_', '.')))
        plt.scatter(0,[start,])
        plt.ylim(start, end)
        plt.xlim(-maxlag, maxlag)
        ax.fmt_ydata = mdates.DateFormatter('%Y-%m-%d')
        Cursor(ax, useblit=True, color='red', linewidth=1.2)


        if outfile:
            if outfile.startswith("?"):
                pair = pair.replace(':','-')
                outfile = outfile.replace('?', '%s-%s-f%i-m%i' % (pair,
                                                                  components,
                                                                  filterid,
                                                                  mov_stack))
            outfile = "ccftime " + outfile
            print "output to:", outfile
            plt.savefig(outfile)
        if show:
            plt.show()
                            

if __name__ == "__main__":
    main()