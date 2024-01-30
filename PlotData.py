from __future__ import print_function

import argparse
import pandas as pd
import h5py
import matplotlib.pyplot as plt
import numpy as np
import scipy.fftpack

def main():

    parser = argparse.ArgumentParser(description='Plots .hdf file from scan.py')
    parser.add_argument('-f','--file', type=str, required=True, help='Filename')
    parser.add_argument('-fft', '--fft', action='store_true', help='Calculates and plots power spectrum')
    parser.add_argument('-tw', '--TWindow', type=float, default=100, help='[sec] time window to average in fft (default=100s)')
    args = parser.parse_args()

    rate = 0
    start_time = 'na'
    end_time = 'na'

    with h5py.File( args.file, "r") as f1:
    # Read attributes from hdf file
        rate = f1.attrs['rate']
        start_time = f1.attrs['start_time']
        end_time = f1.attrs['end_time']
        # In python3, key= list(f1.keys())[0]
        key=f1.keys()[0]
        print("hdf key: ", f1.keys()[0])

    print("Rate: ", rate, "\nStart", start_time, "\nEnd  ", end_time)

    # Read into data frame
    hdf = pd.read_hdf(args.file, key) # THIS CAN BE QUERIED WHILE READ, VERY USEFUL
    channelNames = hdf.columns
    print("Number of events",len(hdf.index))
    print("Number of channels", len(channelNames))

    hdf['time']=np.arange(len(hdf.index))/rate
    # if you want to save 'time' to the existing hdf file,
    # use pd.to_hdf with mode = 'a' and a different key
    # (and when reading from file call the appropriate key)

    print("\nAverage")
    print(hdf.drop('time',axis=1).mean())

    print("\nRMS")
    print(hdf.drop('time',axis=1).std())

    # Ported over from psd_avg_example.py
    if args.fft:
        print("\nCalculating FFT\nTWindow = ",args.TWindow)
        dt = 1.0/rate
        for chan in channelNames:
            (xf, yf) = avg_fft_rms(hdf[chan], dt, args.TWindow)
            # Check that the integral over the PSD gives the same value as time-domain RMS
            print(chan + ': int of yfrms = ', np.sqrt( np.sum(yf[1:]**2) * (xf[1]-xf[0]) ))
            plt.figure()
            plt.semilogy(xf,yf)
            plt.title(chan + ' avg fft rms')

    print("Making plots... ")
    for i in np.arange( len(channelNames) ):
        ax = hdf.plot(x='time', y=channelNames[i], title=channelNames[i], legend=None)
        ax.set_xlabel('t [sec]')
        ax.set_ylabel('[V]')
        plt.grid()



    plt.show()
    return


def avg_fft_rms(ys, dt, Twindow):
    # ys: array of time-domain samples
    # dt: 1/sample rate
    Nwindow = int(Twindow/dt)
    yfsqs = []
    num_windows = len(ys)/Nwindow
    for iwindow in range(num_windows):
        i0 = iwindow*Nwindow
        i1 = (iwindow+1)*Nwindow
        yfs = scipy.fftpack.fft(ys[i0:i1])
        yfsqs.append((2.0*dt/Nwindow)*np.abs(yfs[:Nwindow/2])**2 )
    xf = np.linspace(0.0, 1.0/(2*dt), Nwindow/2)
    yfrms = np.sqrt(np.sum(yfsqs, axis=0)/num_windows)
    return (xf, yfrms)

if ( __name__ == '__main__' ):
    main()