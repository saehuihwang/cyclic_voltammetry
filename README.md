# cyclic_voltammetry

Here, a functional cyclic voltametry (CV) device is presented. A three-electrode electrochemical cell is composed of a working electrode, a reference electrode, and a counter electrode. The working principle of cyclic voltammetry is that a range of voltages is applied to a working electrode and the resulting current is measured. This current can tell us information about an electrochemical redox reaction. Oxidation occurs at the working electrode, reduction occurs at the counter electrode.  

Following conventional CV design, a triangle wave is applied at the working electrode and current flowing between the working and counter electrode is measured. By plotting the current vs applied potential, a traditional "duck plot" can be obtained. 

<img src="https://github.com/saehuihwang/cyclic_voltammetry/blob/main/media/CV_schematic_bb.png" width="700">

### Duck plots
The Randles-Sevcik equation can be used to extract useful information about the electrochemical reaction. Detailed analysis can be found in the project report. 

Below are some examples of duck plots with varying parameters such as scan rate and concentration. 

<img src="https://github.com/saehuihwang/cyclic_voltammetry/blob/main/media/scan_rate.png" width="700">
<img src="https://github.com/saehuihwang/cyclic_voltammetry/blob/main/media/unknown_conc_calibration.png" width="700">


### App & User Interface 
To run the app, run 

  `bokeh serve --show cv_app.py`
  
On the command line.   
The following user interface will show, displaying the scan rate adjusting sliders and a plotting interface 
![alt text](https://github.com/saehuihwang/cyclic_voltammetry/blob/main/media/UI.png?raw=true)
