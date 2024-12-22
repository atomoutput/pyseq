# midi_io.py

import mido
import time

class MIDIOutput:
    def __init__(self, port_name=None):
        if port_name is None:
            outs = mido.get_output_names()
            if not outs:
                raise ValueError("No MIDI output ports available.")
            port_name=outs[0]
        self.port = mido.open_output(port_name)
        print(f"[MIDIOutput] Opened {port_name}")

    def note_on(self, note, velocity=100, channel=1):
        self.port.send(mido.Message('note_on', note=note, velocity=velocity, channel=channel))

    def note_off(self, note, velocity=100, channel=1):
        self.port.send(mido.Message('note_off', note=note, velocity=velocity, channel=channel))

    def close(self):
        self.port.close()


class MIDIInput:
    def __init__(self, engine, port_name=None, ticks_per_quarter=24):
        self.engine=engine
        self.ticks_per_quarter=ticks_per_quarter

        if port_name is None:
            ins = mido.get_input_names()
            if not ins:
                raise ValueError("No MIDI input ports found.")
            port_name=ins[0]

        self.port=mido.open_input(port_name, callback=self.on_midi_in)
        self.last_tick_time=None
        self.clock_intervals=[]
        print(f"[MIDIInput] Listening on {port_name}")

    def on_midi_in(self, msg):
        if msg.type=='clock':
            self.handle_clock()
        elif msg.type in ('start','continue'):
            self.engine.start()
        elif msg.type=='stop':
            self.engine.stop()

    def handle_clock(self):
        now=time.time()
        if self.last_tick_time is None:
            self.last_tick_time=now
            return
        interval=now-self.last_tick_time
        self.last_tick_time=now
        self.clock_intervals.append(interval)
        if len(self.clock_intervals)>100:
            self.clock_intervals.pop(0)
        avg_int=sum(self.clock_intervals)/len(self.clock_intervals)
        if avg_int>0:
            new_bpm=60.0/(avg_int*self.ticks_per_quarter)
            self.engine.set_bpm(new_bpm)

    def close(self):
        self.port.close()
