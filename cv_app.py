"""
Cyclic Voltammetry App

To serve the app, run

    bokeh serve --show cv_app.py

on the command line.
"""

import asyncio
import re
import time

import pandas as pd
import numpy as np

import serial
import serial.tools.list_ports

import bokeh.plotting
import bokeh.io
import bokeh.layouts
import bokeh.driving

bokeh.io.output_notebook()

notebook_url = "localhost:8888"

def find_arduino(port=None):
    """Get the name of the port that is connected to Arduino."""
    if port is None:
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if p.manufacturer is not None and "Arduino" in p.manufacturer:
                port = p.device
    return port


def handshake_arduino(
    arduino, sleep_time=1, print_handshake_message=False, handshake_code=0
):
    """Make sure connection is established by sending
    and receiving bytes."""
    # Close and reopen
    arduino.close()
    arduino.open()

    # Chill out while everything gets set
    time.sleep(sleep_time)

    # Set a long timeout to complete handshake
    timeout = arduino.timeout
    arduino.timeout = 2

    # Read and discard everything that may be in the input buffer
    _ = arduino.read_all()

    # Send request to Arduino
    arduino.write(bytes([handshake_code]))

    # Read in what Arduino sent
    handshake_message = arduino.read_until()

    # Send and receive request again
    arduino.write(bytes([handshake_code]))
    handshake_message = arduino.read_until()

    # Print the handshake message, if desired
    if print_handshake_message:
        print("Handshake message: " + handshake_message.decode())

    # Reset the timeout
    arduino.timeout = timeout


def read_all(ser, read_buffer=b"", **args):
    """Read all available bytes from the serial port
    and append to the read buffer.

    Parameters
    ----------
    ser : serial.Serial() instance
        The device we are reading from.
    read_buffer : bytes, default b''
        Previous read buffer that is appended to.

    Returns
    -------
    output : bytes
        Bytes object that contains read_buffer + read.

    Notes
    -----
    .. `**args` appears, but is never used. This is for
       compatibility with `read_all_newlines()` as a
       drop-in replacement for this function.
    """
    # Set timeout to None to make sure we read all bytes
    previous_timeout = ser.timeout
    ser.timeout = None

    in_waiting = ser.in_waiting
    read = ser.read(size=in_waiting)

    # Reset to previous timeout
    ser.timeout = previous_timeout

    return read_buffer + read


def read_all_newlines(ser, read_buffer=b"", n_reads=4):
    """Read data in until encountering newlines.

    Parameters
    ----------
    ser : serial.Serial() instance
        The device we are reading from.
    n_reads : int
        The number of reads up to newlines
    read_buffer : bytes, default b''
        Previous read buffer that is appended to.

    Returns
    -------
    output : bytes
        Bytes object that contains read_buffer + read.

    Notes
    -----
    .. This is a drop-in replacement for read_all().
    """
    raw = read_buffer
    for _ in range(n_reads):
        raw += ser.read_until()
    return raw


def parse_read2(read):
    """Parse a read with time, and two volage data

    Parameters
    ----------
    read : byte string
        Byte string with comma delimited time/voltage
        measurements.

    Returns
    -------
    time_ms : list of ints
        Time points in milliseconds.
    voltage1 : list of floats
        Voltages in volts.
    voltage2 : list of floats
        Voltages in volts
    remaining_bytes : byte string
        Remaining, unparsed bytes.
    """
    time_ms = []
    voltage1 = []
    voltage2 = []
    temp = []

    # Separate independent time/voltage measurements
    pattern = re.compile(b"\d+|,")
    raw_list = [b"".join(pattern.findall(raw)).decode() for raw in read.split(b"\r\n")]

    for raw in raw_list[:-1]:
        try:
            t, V1, V2 = raw.split(",")
            time_ms.append(int(t))
            voltage1.append(int(V1) * 2 / 1000)  # gain 1 : 1bit = 2mV
            voltage2.append(int(V2) * 2 / 1000)  # gain 1 : 1bit = 2mV

        except:
            pass
    if len(raw_list) == 0:
        return time_ms, voltage1, voltage2, b""
    else:
        return time_ms, voltage1, voltage2, raw_list[-1].encode()


async def daq_stream_async2_cv(
    arduino, data, delay=20, n_trash_reads=5, n_reads_per_chunk=4, reader=read_all
):
    # Receive data
    read_buffer = [b""]

    while True:
        if data["curr_streaming"] == True:
            # Read and throw out first few reads
            i = 0
            while i < n_trash_reads:
                _ = arduino.read_until()
                i += 1

            # Read in chunk of data
            raw = reader(arduino, read_buffer=read_buffer[0], n_reads=n_reads_per_chunk)
            # check if done sweeping
            if b"DONE" in raw:
                data["curr_streaming"] = False
                pass
            else:
                # Parse it, passing if it is gibberish
                try:

                    t, V1, V2, read_buffer[0] = parse_read2(raw)
                    # Update data dictionary
                    data["time_ms"] += t
                    data["Voltage"] += V1
                    data["Current"] += V2
                except:
                    pass

            # Sleep 80% of the time before we need to start reading chunks

        await asyncio.sleep(0.8 * n_reads_per_chunk * delay / 1000)


# Set up connection
HANDSHAKE = 0
START_PAUSE = 4
READ_SWEEPTIME = 5
READ_VLOW = 6
READ_VHIGH = 7
READ_NUM_SCAN = 8
STOP = 9

port = find_arduino()
arduino = serial.Serial(port, baudrate=115200)
handshake_arduino(arduino, print_handshake_message=True)

data = dict(
    prev_array_length=0, curr_streaming=False, time_ms=[], Voltage=[], Current=[]
)


def plot():
    """Build a plot of voltage vs current data"""
    # Set up plot area
    p = bokeh.plotting.figure(
        frame_width=500,
        frame_height=175,
        x_axis_label="voltage (V)",
        y_axis_label="current (mA)",
        title="Voltammogram",
        toolbar_location="above",
    )

    # We'll use whitesmoke backgrounds
    p.border_fill_color = "whitesmoke"

    # Define the data source
    source = bokeh.models.ColumnDataSource(
        data=dict(time_ms=[], Voltage=[], Current=[])
    )

    # Plot traces
    p.circle(source=source, x="Voltage", y="Current", visible=True, color="#f46d43")

    # Put a phantom circle so axis labels show before data arrive
    phantom_source = bokeh.models.ColumnDataSource(
        data=dict(time_ms=[0], Voltage=[0], Current=[0])
    )
    p.circle(source=phantom_source, x="Voltage", y="Current", visible=False)

    return p, source, phantom_source


def controls():
    start_pause = bokeh.models.Button(
        label="start/pause", button_type="success", width=100
    )
    reset = bokeh.models.Button(label="reset", button_type="warning", width=100)

    scanrate_sel = bokeh.models.Slider(
        start=10, end=200, value=160, step=5, title="Scan rate (mV/s)"
    )
    v_range_sel = bokeh.models.RangeSlider(
        start=-1, end=1.5, value=(-1, 0.6), step=0.1, title="Voltage Range (V)"
    )
    numscan_sel = bokeh.models.Slider(
        start=1, end=5, value=1, step=1, title="Number of scans"
    )

    save_notice = bokeh.models.Div(text="<p>No streaming data saved.</p>", width=300)
    save = bokeh.models.Button(label="save", button_type="primary", width=100)
    file_input = bokeh.models.TextInput(
        title="file name", value="filename.csv", width=160
    )

    # Shut down layout
    shutdown = bokeh.models.Button(label="shut down", button_type="danger", width=100)

    return dict(
        start_pause=start_pause,
        reset=reset,
        save=save,
        file_input=file_input,
        save_notice=save_notice,
        shutdown=shutdown,
        scanrate_sel=scanrate_sel,
        numscan_sel=numscan_sel,
        v_range_sel=v_range_sel,
    )


def layout(p, ctrls):
    buttons = bokeh.layouts.row(
        bokeh.models.Spacer(width=30),
        ctrls["start_pause"],
        bokeh.models.Spacer(width=250),
        ctrls["reset"],
    )

    top = bokeh.layouts.column(p, buttons, spacing=15)
    bottom = bokeh.layouts.row(
        ctrls["file_input"], bokeh.layouts.column(ctrls["save_notice"], ctrls["save"])
    )

    left = bokeh.layouts.column(top, bottom)
    right = bokeh.layouts.column(
        bokeh.models.Spacer(width=30),
        ctrls["scanrate_sel"],
        bokeh.models.Spacer(width=30),
        ctrls["v_range_sel"],
        bokeh.models.Spacer(width=30),
        ctrls["numscan_sel"],
    )
    return bokeh.layouts.column(
        bokeh.layouts.row(left, right, background="whitesmoke"), ctrls["shutdown"]
    )


def start_pause_callback(arduino, data, controls):
    data["curr_streaming"] = not data["curr_streaming"]
    arduino.write(bytes([START_PAUSE]))
    disable_param_controls(["scanrate_sel", "numscan_sel", "v_range_sel"], controls)
    arduino.reset_input_buffer()


def scanrate_callback(arduino, controls):
    v_range = controls["v_range_sel"].value[1] - controls["v_range_sel"].value[0] # V
    rate = controls["scanrate_sel"].value # mV/s
    time = round((v_range / rate) * 1000)
    arduino.write(bytes([READ_SWEEPTIME]) + (str(time * 2) + "x").encode())


def v_range_callback(arduino, controls):
    arduino.write(
        bytes([READ_VLOW]) + (str(controls["v_range_sel"].value[0]) + "x").encode()
    )
    arduino.write(
        bytes([READ_VHIGH]) + (str(controls["v_range_sel"].value[1]) + "x").encode()
    )


def numscan_callback(arduino, controls):
    arduino.write(
        bytes([READ_NUM_SCAN]) + (str(controls["numscan_sel"].value) + "x").encode()
    )


def reset_callback(arduino, data, source, phantom_source, controls):
    # Black out the data dictionaries
    arduino.write(bytes([STOP]))
    arduino.reset_input_buffer()
    data["curr_streaming"] = False
    enable_param_controls(["scanrate_sel", "numscan_sel", "v_range_sel"], controls)
    data["time_ms"] = []
    data["Voltage"] = []
    data["Current"] = []

    # Reset the sources
    source.data = dict(time_ms=[], Voltage=[], Current=[])
    phantom_source.data = dict(time_ms=[0], Voltage=[0], Current=[0])
    arduino.reset_input_buffer()


def disable_controls(controls):
    """Disable all controls."""
    for key in controls:
        controls[key].disabled = True


def disable_param_controls(param_names, controls):
    """Disable scan parameter setting controls."""
    for key in param_names:
        controls[key].disabled = True


def enable_param_controls(param_names, controls):
    """Disable scan parameter setting controls."""
    for key in param_names:
        controls[key].disabled = False


def save_callback(data, controls):
    # Convert data to data frame and save
    df_data = pd.DataFrame(
        data={
            "time (ms)": data["time_ms"],
            "Voltage (V)": data["Voltage"] - 1, # digitally shift down to recover actual Sweep voltage
            "Current (mA)": data["Current"] - 2.5, # digitally shift down to recover original TIA current
        }
    )
    df_scaninfo = pd.DataFrame.from_dict(
        {
            "scanrate (mV/s)": controls["scanrate_sel"].value,
            "scan low (V)": controls["v_range_sel"].value[0],
            "scan high (V)": controls["v_range_sel"].value[1],
            "num scan": controls["numscan_sel"].value,
        },
        orient="index",
    ).reset_index()

    df = pd.concat([df_scaninfo, df_data])

    df.to_csv(controls["file_input"].value, index=False)
    # notice text
    notice_text = f"<p> data was last saved to {controls['file_input'].value}.</p>"
    controls["save_notice"].text = notice_text


def shutdown_callback(
    arduino,
    daq_task,
    stream_data,
    stream_controls,
):
    # Disable controls
    disable_controls(stream_controls)

    stream_data["curr_streaming"] = False
    # Stop streaming
    arduino.write(bytes([STOP]))

    # Stop DAQ async task
    daq_task.cancel()

    # Disconnect from Arduino
    arduino.close()


def stream_update(data, source, phantom_source):
    # Update plot by streaming in data
    new_data = {
        "time_ms": np.array(data["time_ms"][data["prev_array_length"] :]) / 1000,
        "Voltage": np.array(data["Voltage"][data["prev_array_length"] :]) - 1, # digitally shift down to recover actual Sweep voltage
        "Current": (np.array(data["Current"][data["prev_array_length"] :]) - 2.5), # digitally shift down to recover original TIA current
    }

    source.stream(new_data)
    # Adjust new phantom data point if new data arrived
    if len(new_data["time_ms"] > 0):
        phantom_source.data = dict(
            time_ms=[new_data["time_ms"][-1]],
            Voltage1=[new_data["Voltage"][-1]],
            Voltage2=[new_data["Current"][-1]],
        )
    data["prev_array_length"] = len(data["time_ms"])


def cv_app(
    arduino,
    stream_data,
    daq_task,
    stream_plot_delay=1,
):
    def _app(doc):
        try:
            # Controls
            stream_controls = controls()

            # Plots
            p_stream, stream_source, stream_phantom_source = plot()

            # Layouts
            stream_layout = layout(p_stream, stream_controls)

            app_layout = bokeh.layouts.column(stream_layout, background="whitesmoke")

            def _start_pause_callback(event=None):
                start_pause_callback(arduino, stream_data, stream_controls)

            def _reset_callback(event=None):
                reset_callback(
                    arduino,
                    stream_data,
                    stream_source,
                    stream_phantom_source,
                    stream_controls,
                )

            def _save_callback(event=None):
                save_callback(stream_data, stream_controls)

            def _shutdown_callback(event=None):
                shutdown_callback(
                    arduino,
                    daq_task,
                    stream_data,
                    stream_controls,
                )

            def _scanrate_callback(attr, old, new):
                scanrate_callback(arduino, stream_controls)

            def _v_range_callback(attr, old, new):
                v_range_callback(arduino, stream_controls)

            def _numscan_callback(attr, old, new):
                numscan_callback(arduino, stream_controls)

            @bokeh.driving.linear()
            def _stream_update(step):
                stream_update(stream_data, stream_source, stream_phantom_source)

            # Link callbacks
            stream_controls["start_pause"].on_click(_start_pause_callback)
            stream_controls["reset"].on_click(_reset_callback)
            stream_controls["save"].on_click(_save_callback)
            stream_controls["shutdown"].on_click(_shutdown_callback)
            stream_controls["scanrate_sel"].on_change("value", _scanrate_callback)
            stream_controls["v_range_sel"].on_change("value", _v_range_callback)
            stream_controls["numscan_sel"].on_change("value", _numscan_callback)

            # Add the layout to the app
            doc.add_root(app_layout)

            # Add a periodic callback, monitor changes in stream data
            pc = doc.add_periodic_callback(_stream_update, stream_plot_delay)
        except Exception as e:
            print(e)

    return _app


# Set up asynchronous DAQ task
daq_task = asyncio.create_task(daq_stream_async2_cv(arduino, data))

# Build app
app = cv_app(arduino, data, daq_task)

# Build it with curdoc
app(bokeh.plotting.curdoc())
