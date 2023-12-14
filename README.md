# EnergyMeter
EnergyMeter is a Python module that combines pyRAPL, NVIDIA-SMI and eBPF to estimate the energy consumption of CPU, memory, GPU, and storage on Linux with only three lines of code.

## How to use
The most basic usage of EnergyMeter is as follows:
```
from energy_meter import EnergyMeter

em = EnergyMeter(disk_avg_speed=1600*1e6, # The average speed of your storage (see below how you can get it)
                  disk_active_power=6,    # How many Watts are used when the storage is reading or writing (you can usually find it in specs of your storage)
                  disk_idle_power=1.42,   # How many Watts are used when the storage is idle (you can usually find it in specs of your storage)
                  label="Test Meter",     # A label to identify the measurement
                  include_idle=False)     # If energy used during idle should be accounted for in the measurement. Defaults to False.
    
em.begin()
# --> CODE YOU WANT TO MEASURE <--
em.end()

# Plot energy consumption per component.
meter.plot_total_jules_per_component()
# or print(em.get_total_joules_per_component())
```
![Example Output](https://github.com/maufadel/meml/blob/main/example_output.png)

You can check the notebook [Measuring_energy_consumption.ipynb](https://github.com/maufadel/meml/blob/main/Measuring_energy_consumption.ipynb) for more details.

## How to get storage details
You can benchmark your storage speed with the Flexible I/O tester (FIO) as recommended by Google in the following tutorial: https://cloud.google.com/compute/docs/disks/benchmarking-pd-performance 

Storage specs usually include data regarding the power consumption during active (reading or writing) and for idle periods.

## Troubleshooting
pyRAPL requires access to /sys/class/powercap/intel-rapl, for which sudo access is required. If the access is denied, run the following command on the terminal to enable access to the rapl measurement:
`sudo chmod -R a+r /sys/class/powercap/intel-rapl`.

## Limitations
EnergyMeter requires to be run on bare metal instances running Linux on Intel and NVIDIA hardware. These requirements are inherited from the tools used for tracking the energy consumption: RAPL (Intel), NVIDIA-SMI (NVIDIA), and eBPF (Linux). Keep in mind that the energy consumption metrics provided are estimations and vary according to different factors including hardware configuration and software versions. Additionally, the energy consumed by cooling, screens and other components not mentioned here are not included in our measurements, so the total energy consumed will likely be different to the total sum of the consumption of CPU, memory, GPU, and storage.

## Authorship and License
I am developing EnergyMeter as a part of my PhD program at Universidad Politécnica de Madrid. EnergyMeter is open sourced under an MIT License. 
