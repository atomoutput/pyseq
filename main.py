# main.py

import tkinter as tk
from track import Track
from engine import SequencerEngine
from midi_io import MIDIOutput
from gui import GridSequencerGUI

def main():
    # Create a couple of tracks
    track1 = Track(name="Cantus Firmus", step_count=8, channel=1, subdivisions=2)
    track1.algorithm = "euclidean"
    track1.generative_params = {"pulses":4}
    track1.generate_pattern()

    track2 = Track(name="Counterpoint", step_count=8, channel=2, subdivisions=2)
    track2.algorithm = "counterpoint"
    track2.generative_params = {"species":"1st","intervals":[3,4,7,12],"avoid_parallel":True}

    engine = SequencerEngine(bpm=120)
    engine.add_track(track1)
    engine.add_track(track2)

    # default global MIDI out
    midi_out = MIDIOutput()
    engine.midi_output = midi_out

    root = tk.Tk()
    app = GridSequencerGUI(root, engine)
    root.mainloop()

    midi_out.close()

if __name__=="__main__":
    main()
