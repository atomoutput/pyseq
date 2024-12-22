# engine.py

import time
import threading
from midi_io import MIDIOutput

class SequencerEngine:
    def __init__(self, bpm=120, tracks=None, midi_output=None):
        self._bpm = bpm
        self.tracks = tracks if tracks else []
        self.midi_output = midi_output  # This is a fallback or “global default.”

        self.playing = False
        self.sequencer_thread = None
        self.clock_resolution = 100

        self.current_steps = {}
        for i,_ in enumerate(self.tracks):
            self.current_steps[i]=0

        # callback: on_step_callback(track_idx, step)
        self.on_step_callback = None

    @property
    def bpm(self):
        return self._bpm

    def set_bpm(self, new_bpm):
        if new_bpm<1:
            new_bpm=1
        self._bpm=new_bpm

    def add_track(self, track):
        idx=len(self.tracks)
        self.tracks.append(track)
        self.current_steps[idx]=0

    def remove_track(self, track_idx):
        if 0<=track_idx<len(self.tracks):
            del self.tracks[track_idx]
            # re-build current_steps map
            self.current_steps={}
            for i,_ in enumerate(self.tracks):
                self.current_steps[i]=0

    def reorder_tracks(self, old_index, new_index):
        """
        Move track from old_index to new_index (drag & drop style).
        """
        if old_index<0 or old_index>=len(self.tracks):
            return
        if new_index<0 or new_index>=len(self.tracks):
            return
        track=self.tracks.pop(old_index)
        self.tracks.insert(new_index, track)
        # re-build current_steps
        cpy = {}
        for i,_ in enumerate(self.tracks):
            cpy[i]=0
        self.current_steps=cpy

    def generate_all_tracks(self):
        ref = self.tracks[0] if self.tracks else None
        for t in self.tracks:
            if t.algorithm=="counterpoint":
                t.generate_pattern(reference_track=ref)
            else:
                t.generate_pattern()

    def start(self):
        if self.playing:
            return
        self.playing=True
        if not self.sequencer_thread or not self.sequencer_thread.is_alive():
            self.sequencer_thread = threading.Thread(target=self.run)
            self.sequencer_thread.start()
        print("[Engine] Started.")

    def stop(self):
        self.playing=False
        if self.sequencer_thread and self.sequencer_thread.is_alive():
            self.sequencer_thread.join()
        self.sequencer_thread=None
        for i in range(len(self.tracks)):
            self.current_steps[i]=0
        print("[Engine] Stopped.")

    def run(self):
        track_accum=[0.0]*len(self.tracks)
        track_interval=[0.0]*len(self.tracks)

        for i,tr in enumerate(self.tracks):
            track_interval[i]=60.0/(self._bpm*tr.subdivisions)
        tick_dur=1.0/self.clock_resolution

        while self.playing:
            for i, track in enumerate(self.tracks):
                track_accum[i]+=tick_dur
                if track_accum[i]>=track_interval[i]:
                    track_accum[i]-=track_interval[i]
                    old_step=self.current_steps[i]
                    new_step=(old_step+1)%track.step_count
                    self.current_steps[i]=new_step

                    step_data=track.steps[new_step]
                    if step_data["active"]==1:
                        # Use track-specific MIDI device if set, else engine's default
                        output_device = None
                        if track.midi_output_device:
                            output_device = MIDIOutput(track.midi_output_device)
                        else:
                            output_device = self.midi_output

                        if output_device:
                            note=step_data["note"]
                            vel=step_data["velocity"]
                            output_device.note_on(note, vel, track.channel)
                            # schedule note_off
                            threading.Timer(0.15, output_device.note_off,
                                            args=(note, vel, track.channel)).start()

                            # if it's track-specific, close after usage
                            if track.midi_output_device:
                                output_device.close()

                    if self.on_step_callback:
                        self.on_step_callback(i,new_step)

            time.sleep(tick_dur)

    # Device selection for engine-wide output
    def set_midi_output_device(self, device_name):
        if self.midi_output:
            self.midi_output.close()
        from midi_io import MIDIOutput
        self.midi_output=MIDIOutput(device_name)
        print(f"[Engine] Default MIDI output -> {device_name}")

    def set_midi_input_device(self, device_name):
        from midi_io import MIDIInput
        if not device_name or device_name=="Internal (No Clock)":
            print("[Engine] Using internal clock only.")
            return
        try:
            midi_in=MIDIInput(engine=self, port_name=device_name)
            print(f"[Engine] MIDI input -> {device_name}")
        except Exception as e:
            print(f"[Engine] Error opening MIDI input: {e}")
