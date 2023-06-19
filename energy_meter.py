#!/usr/bin/env python
"""
This module implements the class EnergyMeter, to measure the energy consumption 
of Python functions or code chunks, segregating their energy usage per component
(CPU, DRAM, GPU and Hard Disk). 
"""
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyRAPL

class EnergyMeter:
    """
    The consumption of each component is measured as follows:

    - CPU: the energy consumption of the CPU is measured with RAPL via the pyRAPL
        library. RAPL is an API from Intel, which is also semi-compatible with
        AMD. RAPL on Intel has been shown to be accurate thanks to the usage of
        embedded sensors in the processor and memory while AMD uses performance
        counters and is therefore, not so accurate.
        
    - DRAM: the energy used by the memory is also measure with RAPL via pyRAPL.
        This might not be available for AMD processors and pre-Haswell Intel
        processors. You can find more info here: 
        https://dl.acm.org/doi/pdf/10.1145/2989081.2989088.
    
    - GPU: we measure the energy consumption of the GPU with nvidia-smi. Note that
        for now, you should run the bash script start_meters.sh on your own BEFORE
        starting a meter. This bash script will create a folder with a csv file that
        contains the power consumption that will then be used to measure the energy
        consumption of the GPU while the function or code chunk was running.
    
    - Disk: we cannot directly measure the energy consumption of the disk in the same
        way that we do for the other components, so we have implemented an bpftrace
        probe that tracks all the bytes read and written to disk. This probe will
        be launched by the bash script start_meters.sh and will create another csv
        file that is saved along the csv for the GPU stats. We then calculated the
        energy consumption with the following formulae:
        disk_active_time = (bytes_read + bytes_written) / DISK_SPEED
        disk_idle_time = total_meter_time - disk_active_time
        total_energy = disk_active_time * DISK_ACTIVE_POWER + 
                        disk_idle_time * DISK_IDLE_POWER
        Note that you are required the provide the parameters DISK_SPEED, 
        DISK_ACTIVE_POWER and DISK_IDLE_POWER.
    """
    def __init__(self, disk_avg_speed, disk_active_power, disk_idle_power, label=None):
        """Initiates the variables required to meter the energy consumption of all
        components and sets up the pyRAPL library.
        :param disk_avg_speed: the average read and write speed of the hard disk where
            the code will be run. We recommend measuring this with a speed test such as
            this: https://cloud.google.com/compute/docs/disks/benchmarking-pd-performance.
        :param disk_active_power: the power used by the disk when active. This information
            is usually included in the disk specs. Hint: run lshw to get info about the
            host's disk.
        :param disk_idle_power: the average power used by the disk when idle. Just as for
            disk_active_power, this is usually included in the disk specs.
        :param label: this is just an optional string to identify the meter.
        """
        pyRAPL.setup()

        self.disk_avg_speed = disk_avg_speed
        self.disk_active_power = disk_active_power
        self.disk_idle_power = disk_idle_power
        
        self.meter = None
        if label:
            self.label = label
        else:
            self.label = "Meter"

    def begin(self):
        """Begin measuring the energy consumption. This sets the starting datetime and
        reads the current RAPL counters. You should have start the bash script 
        start_meters.sh BEFORE calling this function.
        """
        self.meter = pyRAPL.Measurement(self.label)
        self.meter.begin()

    def end(self):
        """Finish the measurements and calculate results for CPU and DRAM. This sets the
        duration of the meter and reads again the RAPL counters, calculating how much energy
        was used since the meter began. You should stop running the bash script 
        start_meters.sh AFTER calling this method.
        """
        self.meter.end()

    def get_total_jules_disk(self, filename):
        """We calculate the disk's energy consumption while the meter was running. For this,
        we require the csv file that was generated by running the bash script start_meters.sh.
        In this case, we utilize the speed and energy consumption parameters given when this
        object was initiated to estimate the disk's energy consumption.
        :param filename: the path to the csv file generated by start_meters.sh (or where the 
            output of disk_io.bt was saved.)
        :returns: the total jules used by the disk between meter.begin() and meter.end().
        """
        # TODO: headers are wrongly read by pandas, fix this.
        df = pd.read_csv(filename, skiprows=[0], sep=";")
        df.index = pd.to_datetime(df.index)
        meter_start = datetime.fromtimestamp(self.meter.result.timestamp)
        meter_end = datetime.fromtimestamp(self.meter.result.timestamp + 
                                               self.meter.result.duration*1e-6)
        filtered_df = df[(df.index >= meter_start) & (df.index < meter_end)]
        
        tot_bytes = filtered_df[filtered_df["ByteSize"].str.contains("python")]["Operation"].sum()
        
        # disk_active_time (in seconds) = (bytes_read + bytes_written) / DISK_SPEED
        disk_active_time = (tot_bytes / self.disk_avg_speed)
        
        # disk_idle_time (in seconds) = total_meter_time - disk_active_time
        disk_idle_time = self.meter.result.duration * 1e-6 - disk_active_time
        
        # total_energy = disk_active_time * DISK_ACTIVE_POWER + disk_idle_time * DISK_IDLE_POWER
        return  disk_active_time * self.disk_active_power + disk_idle_time * self.disk_idle_power

    def get_total_jules_cpu(self):
        """We obtain the total jules consumed by the CPU from pyRAPL.
        :returns: the total jules used by the CPU between meter.begin() and meter.end().
        """
        # pyRAPL returns the microjules, so we convert them to jules.
        return np.array(self.meter.result.pkg) * 1e-6


    def get_total_jules_dram(self):
        """We obtain the total jules consumed by the DRAM from pyRAPL.
        :returns: the total jules used by the DRAM between meter.begin() and meter.end().
        """
        # pyRAPL returns the microjules, so we convert them to jules.
        return np.array(self.meter.result.dram) * 1e-6
    
    
    def get_total_jules_gpu(self, filename):
        """We calculate the GPU's energy consumption while the meter was running. For this,
        we require the csv file that was generated by running the bash script start_meters.sh.
        This is calculated as the mean power used between meter.begin() and meter.end() times
        the total time in seconds.
        :param filename: the path to the csv file generated by start_meters.sh (or the file 
            generated by gpu_stats.sh.)
        :returns: the total jules used by the GPU between meter.begin() and meter.end().
        """
        df = pd.read_csv(filename)
        df.timestamp = pd.to_datetime(df.timestamp)
        meter_start = datetime.fromtimestamp(self.meter.result.timestamp)
        meter_end = datetime.fromtimestamp(self.meter.result.timestamp + 
                                               self.meter.result.duration*1e-6)
        mean_p = df[(df.timestamp >= meter_start) & (df.timestamp < meter_end)]["power_usage(W)"].mean()
        return mean_p * self.meter.result.duration * 1e-6
    
    def get_total_jules_per_component(self, foldername):
        """This returns the total energy consumption in jules between meter.begin() and meter.end()
        segregated by component (CPU, DRAM, GPU and disk).
        :param foldername: the path to the folder generated by start_meters.sh.
        :returns: a dictionary with the total jules used by each component.
        """
        cpu = self.get_total_jules_cpu()
        dram = self.get_total_jules_dram()
        gpu = self.get_total_jules_gpu(foldername + "/gpu_stats.csv")
        if np.isnan(gpu):
            gpu = 0
        disk = self.get_total_jules_disk(foldername + "/disk_stats.csv")
        res = { "cpu": cpu,
                "dram": dram,
                "gpu": gpu,
                "disk": disk,
              }
        return res

    def plot_total_jules_per_component(self, foldername):
        """This plots the total energy consumption in jules between meter.begin() and meter.end()
        and the total consumption by each component (CPU, DRAM, GPU and disk).
        :param foldername: the path to the folder generated by start_meters.sh.
        """
        data = self.get_total_jules_per_component(foldername)
        data["total"] = np.sum(data.get("cpu")) + np.sum(data.get("dram")) + data.get("disk") + data.get("gpu")
        keys = data.keys()
        values = [float(val) for val in data.values()]
        
        plt.bar(keys, values)
        plt.xlabel('Components')
        plt.ylabel('Jules')
        plt.title(self.meter.label)
        
        plt.show()
