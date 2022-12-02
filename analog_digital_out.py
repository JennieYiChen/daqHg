#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
Sends ramping instructions to a MCUSB daq and live plots
"""
import math, time, sys, os, h5py, collections
import numpy as np

from uldaq import (
    DaqDevice,
    create_float_buffer,
    get_daq_device_inventory,
    InterfaceType,
    AOutScanFlag,
    ScanOption,
    ScanStatus,
    DigitalDirection,
    DigitalPortIoType,
    DigitalPortType,
    AInScanFlag,
    AiInputMode,
    Range,
    DaqEventType,
    WaitType,
    ULException,
    EventCallbackArgs,
    DaqOutScanFlag,
    DaqOutChanType, 
    DaqOutChanDescriptor
)

PROBE_MODE = 1
PUMP_MODE = 0

def main():
    mode = PUMP_MODE
    
    interface_type = InterfaceType.ANY
    descriptor_index = 0 # Use the first detected DAQ device 
    
    # Parameters for AoDevice.a_out_scan
    ao_low_channel = 0
    ao_high_channel = 0
    voltage_range_index = 0  # Use the first supported range
    number_of_channels = ao_high_channel - ao_low_channel + 1
    ao_samples_per_channel = 3000  
    ao_sample_rate = 1000  # Hz
    ao_scan_options = ScanOption.SINGLEIO
    ao_scan_flags = AOutScanFlag.DEFAULT
    scan_status = ScanStatus.IDLE
    
    # Parameters for ananlog input 
    range_index = 0
    ai_low_channel = 0
    ai_high_channel = 1
    input_mode = AiInputMode.DIFFERENTIAL
    range_index = 0
    ai_samples_per_channel = 10000
    ai_rate = 100
    ai_available_sample_count = 2000
    ai_scan_options = ScanOption.CONTINUOUS
    ai_flags = AInScanFlag.DEFAULT
    ai_channel_count = ai_high_channel - ai_low_channel + 1

    # three event trigger conditions
    event_types = (DaqEventType.ON_DATA_AVAILABLE 
        | DaqEventType.ON_END_OF_INPUT_SCAN 
        | DaqEventType.ON_INPUT_SCAN_ERROR)

    # parameter titles in a_in_scan_events callback function
    scan_params = collections.namedtuple('scan_params', 
        'buffer ai_low_chan ai_high_chan ai_available_sample_count')
  
    # Get descriptors for all of the available DAQ devices.
    try:
        devices = get_daq_device_inventory(interface_type) 
        number_of_devices = len(devices)
        # Verify at least one DAQ device is detected.
        if number_of_devices == 0:
            raise RuntimeError('Error: No DAQ devices found')

        print('Found', number_of_devices, 'DAQ device(s):')
        for i in range(number_of_devices):
            print('  [', i, '] ', devices[i].product_name, ' (',
                  devices[i].unique_id, ')', sep='')    
    
        # Create the DAQ device
        daq_device = DaqDevice(devices[descriptor_index])
        ao_device = daq_device.get_ao_device()
        ai_device = daq_device.get_ai_device()
        dio_device = daq_device.get_dio_device()

        # Establish a connection to the device.
        # For Ethernet devices using a connection_code other than the default value of zero, change the line below to enter the desired code.
        daq_device.connect(connection_code=0)
                
        # Create an array for output data. Analog Out
        out_buffer = create_float_buffer(number_of_channels, ao_samples_per_channel)

        # Configure the port for output. Digital
        dio_device.d_config_port(DigitalPortType.AUXPORT, DigitalDirection.OUTPUT)
       
        # Get a list of supported ranges and validate the range index
        ranges = ai_device.get_info().get_ranges(input_mode)
        if range_index >= len(ranges):
            range_index = len(ranges) - 1
        
        # Allocate a buffer to receive the data. Analog In
        data = create_float_buffer(ai_channel_count, ai_samples_per_channel)
       
        # parameters in a_in_scan_events callback function
        user_data = scan_params(
            data, 
            ai_low_channel,
            ai_high_channel, 
            ai_available_sample_count)
        
        # Enable the a_in_scan_events function
        daq_device.enable_event(
            event_types, 
            ai_available_sample_count, 
            event_callback_function, 
            user_data
        ) 
        
        
        input("\nHit ENTER to continue")

        # start the acquisition.
        ai_rate = ai_device.a_in_scan(
            ai_low_channel,
            ai_high_channel,
            input_mode,
            ranges[range_index],
            ai_samples_per_channel,
            ai_rate,
            ScanOption.CONTINUOUS, 
            AInScanFlag.DEFAULT,
            data
        )
        
        # Setting things up.    
        dio_device.d_out(
            DigitalPortType.AUXPORT, 0
        ) # DIO 4 low = disable the integrator (unlock); DIO 5 low = pump setpoint
        time.sleep(0.1)
        dio_device.d_out(
            DigitalPortType.AUXPORT, 32
        ) # DIO 4 low = disable the integrator (unlock); DIO 5 high = probe setpoint
        create_output_ramp (
            SwitchToProbe = 1, out = 0, shift = 4.16, data_buffer = out_buffer
        ) # GoToProbe, AO ramp up
   
        # Start the output scan.
        ao_sample_rate = ao_device.a_out_scan(
            ao_low_channel, 
            ao_high_channel,
            ao_device.get_info().get_ranges()[voltage_range_index],
            ao_samples_per_channel,
            ao_sample_rate,
            ao_scan_options,
            ao_scan_flags,
            out_buffer
        )  # reading only 1 and the 1st channel; 1000 Hz and 2 s buffer
           # out_buffer to be upper level?
        #print(out_buffer[2999])
          
                                           
        # time.sleep(2.5) #0.6
        time.sleep(2.5)
        dio_device.d_out(DigitalPortType.AUXPORT, 48
        ) # DIO 4 high = connect the integrator (lock); DIO 5 high = probe setpoint 
        
        mode = PROBE_MODE
        
        input("\nPress Enter to Ramp down\n") 
        #print(*(out_buffer))
       
        if (
            mode == PROBE_MODE
        ): # probe frequency, go to probe (ramp up) (0,32, ramp, 48)
            dio_device.d_out(
                DigitalPortType.AUXPORT, 32
            ) # DIO 4 low = disable the integrator (unlock); DIO 5 high = probe setpoint
            time.sleep(0.1)
            dio_device.d_out(
                DigitalPortType.AUXPORT, 0
            ) # DIO 4 low = disable the integrator (unlock); DIO 5 low = pump setpoint 
            out_buffer = create_output_ramp(
                SwitchToProbe = 0, out = 4.16, shift = 4.16, data_buffer = out_buffer
            ) # GoToPump, ramp down, value = 4.16 temp
          
            # Start the output scan.
            scan_status, transfer_status = ao_device.get_scan_status()
            if scan_status == ScanStatus.RUNNING:
                ao_device.scan_stop()
            ao_sample_rate = ao_device.a_out_scan(
                ao_low_channel,
                ao_high_channel,
                ao_device.get_info().get_ranges()[voltage_range_index],
                ao_samples_per_channel,
                ao_sample_rate,
                ao_scan_options,
                ao_scan_flags,
                out_buffer)
         
            #time.sleep(2.5) #0.6
            time.sleep(2.5) 
            mode = PUMP_MODE

       
    except Exception as e:
        print("\n", e)     

    finally:       
        if daq_device:
            print('daq_device Check')
            # Stop the ao scan.
            if scan_status == ScanStatus.RUNNING:
                ao_device.scan_stop()
                print('ao_scan_stop')
            # before disconnecting, set the port back to input
            dio_device.d_config_port(DigitalPortType.AUXPORT, DigitalDirection.INPUT)
                       
            # Disconnect from the DAQ device.
            if daq_device.is_connected():
                if ai_device and ai_device.get_info() and ai_device.get_info().has_pacer():
                    ai_device.scan_stop()
                    # f.close() # close the hdf5 file
                daq_device.disable_event(event_types)
                daq_device.disconnect()          
            # Release the DAQ device resource.
            daq_device.release()
    
def create_output_ramp(SwitchToProbe, out, shift, data_buffer):
    """Populate the buffer with a ramp: overshoot, stay , back to target, then stay."""
    num_points = 3000
    first_phase = 1170
    second_phase = 1280
    third_phase = 1450
    shift_denom = 999
    for i in range(num_points):
        if i < first_phase:
            if SwitchToProbe == 1:
                data_buffer[i] = i*(shift/shift_denom)
            else:
                data_buffer[i] = 1.0 * out - i*(shift/shift_denom)
        if second_phase > i >= first_phase:
            data_buffer[i] = data_buffer[i - 1]
        if third_phase > i >= second_phase:
            if SwitchToProbe == 1:
                data_buffer[i] = data_buffer[i - 1] - (shift / shift_denom)
            else:
                data_buffer[i] = data_buffer[i - 1] + (shift / shift_denom)
        if num_points > i >= third_phase:
            if SwitchToProbe == 1:
                data_buffer[i] = shift
            else:
                data_buffer[i] = 1.0 * out - shift
                
    return data_buffer

def event_callback_function(event_callback_args):
    
    event_type = DaqEventType(event_callback_args.event_type)
    event_data = event_callback_args.event_data
    user_data = event_callback_args.user_data

    if (event_type == DaqEventType.ON_DATA_AVAILABLE
            or event_type == DaqEventType.ON_END_OF_INPUT_SCAN):
        
        print('\n')
        chan_count = user_data.ai_high_chan - user_data.ai_low_chan + 1
        scan_count = event_data
        total_samples = scan_count * chan_count

        buffer_len = len(user_data.buffer) 

        startIndex = ((scan_count - user_data.ai_available_sample_count) * chan_count) % buffer_len # (n*2000-2000)*num_chan%(2*3000)
        endIndex = (scan_count * chan_count) % buffer_len #  n*2000*num_chan%(2*3000)
        
        if (endIndex < startIndex):
            data = np.append(user_data.buffer[startIndex:], user_data.buffer[:endIndex])
        else:  
            data = user_data.buffer[startIndex:endIndex]
        
        data = np.reshape(data,(-1,chan_count))
        
        new_shape = (scan_count, chan_count)

        # Print outputs
        print('Event counts (total): ', scan_count)
        #print('Scan rate = ', '{:.2f}'.format(DAQ.rate), 'Hz')
        print('buffer_length = ', buffer_len)
        print('currentBufferIndex = ', startIndex)
        print('user_data.buffer_store = ', user_data.ai_available_sample_count)
        print('endIndex = ', endIndex)
        for i in range(chan_count):
            print('chan',
                  i + user_data.ai_low_chan,
                  '{:.6f}'.format(user_data.buffer[endIndex - chan_count + i]))
                  
        # print('currentIndex = ', index, '\n')

        # for i in range(chan_count):
        #     clear_eol()
        #     print('chan =',
        #           i + user_data.low_chan,
        #          '{:10.6f}'.format(user_data.buffer[index + i]))

    if event_type == DaqEventType.ON_INPUT_SCAN_ERROR:
        exception = ULException(event_data)
        print(exception)
        user_data.status['error'] = True

    if event_type == DaqEventType.ON_END_OF_INPUT_SCAN:
        print('\nThe scan is complete\n')
        user_data.status['complete'] = True

if __name__ == '__main__':
    main()
