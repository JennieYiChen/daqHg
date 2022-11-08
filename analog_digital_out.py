#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
Sends ramping instructions to a MCUSB daq and live plots
"""
import math, time, sys, os

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
)

PROBE_MODE = 1
PUMP_MODE = 0

def main():
    mode = PUMP_MODE
    
    interface_type = InterfaceType.ANY
    descriptor_index = 0
    
    # Parameters for AoDevice.a_out_scan
    low_channel = 0
    high_channel = 0
    voltage_range_index = 0  # Use the first supported range
    number_of_channels = 1
    samples_per_channel = 3000  
    sample_rate = 1000  # Hz
    #scan_options = ScanOption.SINGLEIO
    #scan_flags = AOutScanFlag.DEFAULT
    scan_status = ScanStatus.IDLE
    

    range_index = 0
    ai_low_channel = 0
    ai_high_channel = 0
    ai_samples_per_channel = 10000
    ai_rate = 100
    ai_channel_count = ai_high_channel - ai_low_channel + 1

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
        out_buffer = create_float_buffer(number_of_channels = 1, samples_per_channel = 3000)

        # Configure the port for output. Digital
        dio_device.d_config_port(DigitalPortType.AUXPORT, DigitalDirection.OUTPUT)
        
        # Allocate a buffer to receive the data
        data = create_float_buffer(ai_channel_count, ai_samples_per_channel = 10000)
        
        
        input("\nHit ENTER to continue")

        # start the acquisition.
        ai_rate = ai_device.a_in_scan(
            low_channel,
            high_channel,
            input_mode, 
            ranges[range_index],
            ai_samples_per_channel,
            ai_rate,
            ScanOption.CONTINUOUS, 
            AInScanFlag.DEFAULT,
            data
        )


        # TODO: test d_out. What is 0, 32, 48??
        # Setting things up.    
        dio_device.d_out(
            DigitalPortType.AUXPORT, 0
        ) # DIO 4 low = disable the integrator (unlock); DIO 5 low = pump setpoint
        time.sleep(0.1)
        dio_device.d_out(
            DigitalPortType.AUXPORT, 32
        ) # DIO 4 low = disable the integrator (unlock); DIO 5 high = probe setpoint
        out_buffer = create_output_ramp(
            SwitchToProbe = 1, out = 0, shift = 4.16, data_buffer = out_buffer
        ) # GoToProbe, AO ramp up
   
        # Start the output scan.
        sample_rate = ao_device.a_out_scan(
            low_channel, 
            high_channel,
            ao_device.get_info().get_ranges()[voltage_range_index],
            samples_per_channel,
            sample_rate,
            ScanOption.SINGLEIO,
            AOutScanFlag.DEFAULT,
            out_buffer
        )  # reading only 1 and the 1st channel; 1000 Hz and 2 s buffer
           # out_buffer to be upper level?
        #print(out_buffer[2999])
          
                                           
        time.sleep(2.5) #0.6
        dio_device.d_out(DigitalPortType.AUXPORT, 48
        ) # DIO 4 high = connect the integrator (lock); DIO 5 high = probe setpoint 
        
        mode = PROBE_MODE
        
        input("\nPress Enter to Ramp down\n") 
        #print(*(out_buffer))
       
        if (
            mode == PROBE_MODE
        ): # probe frequency, go to probe (ramp up) (0,32, ramp, 48)
            dio_device.d_out(DigitalPortType.AUXPORT, 32)
            time.sleep(0.1)
            dio_device.d_out(DigitalPortType.AUXPORT, 0)  
            out_buffer = create_output_ramp(
                SwitchToProbe = 0, out = 4.16, shift = 4.16, data_buffer = out_buffer
            ) # GoToPump, ramp down, value = 4.16 temp
          
            # Start the output scan.
            scan_status, transfer_status = ao_device.get_scan_status()
            if scan_status == ScanStatus.RUNNING:
                ao_device.scan_stop()
            sample_rate = ao_device.a_out_scan(
                low_channel,
                high_channel,
                ao_device.get_info().get_ranges()[voltage_range_index],
                samples_per_channel,
                sample_rate,
                ScanOption.SINGLEIO,
                AOutScanFlag.DEFAULT, out_buffer)
         
            time.sleep(2.5) #0.6
            mode = PUMP_MODE

       
    except Exception as e:
        print("\n", e)     

    finally:       
        if daq_device:
            # Stop the scan.
            if scan_status == ScanStatus.RUNNING:
                ao_device.scan_stop()
                print('scan_stop')
            # before disconnecting, set the port back to input
            dio_device.d_config_port(DigitalPortType.AUXPORT, DigitalDirection.INPUT)
                        
            # Disconnect from the DAQ device.
            if daq_device.is_connected():
                daq_device.disconnect()
            # Release the DAQ device resource.
            daq_device.release()
    
def create_output_ramp(SwitchToProbe, out, shift, data_buffer):
    """Populate the buffer with a ramp for only one channel."""
    num_points = 3000
    for i in range(num_points):
        if SwitchToProbe == 1:
            data_buffer[i] = i*(shift/(num_points-1))
        else:
            data_buffer[i] = 1.0 * out - i*(shift/(num_points-1))
    
    return data_buffer


if __name__ == '__main__':
    main()
