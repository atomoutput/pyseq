# track.py

import random

###################################
# NOTE NAME MAPPING
###################################
NOTE_NAMES = [
    "C1","C#1","D1","D#1","E1","F1","F#1","G1","G#1","A1","A#1","B1",
    "C2","C#2","D2","D#2","E2","F2","F#2","G2","G#2","A2","A#2","B2",
    "C3","C#3","D3","D#3","E3","F3","F#3","G3","G#3","A3","A#3","B3",
    "C4","C#4","D4","D#4","E4","F4","F#4","G4","G#4","A4","A#4","B4",
    "C5","C#5","D5","D#5","E5","F5","F#5","G5","G#5","A5","A#5","B5",
    "C6","C#6","D6","D#6","E6","F6","F#6","G6","G#6","A6","A#6","B6",
    "C7","C#7","D7","D#7","E7","F7","F#7","G7","G#7","A7","A#7","B7",
]

def note_name_to_midi(name: str) -> int:
    try:
        idx = NOTE_NAMES.index(name)
        # C1 => MIDI 24
        return 24 + idx
    except ValueError:
        return 60  # fallback to C4

def midi_to_note_name(midi_num: int) -> str:
    base = midi_num - 24
    if base < 0:
        base = 0
    if base >= len(NOTE_NAMES):
        base = len(NOTE_NAMES) - 1
    return NOTE_NAMES[base]

###################################
# TRACK CLASS
###################################
class Track:
    """
    Each step: {"active":0/1, "note":int, "velocity":int}
    Each track can store its own 'midi_output_device' string if the user
    wants a separate MIDI out, or None to use the engine's default.
    """
    def __init__(self, name, step_count=16, channel=1, subdivisions=4):
        self.name = name
        self.channel = channel
        self.step_count = step_count
        self.subdivisions = subdivisions
        self.algorithm = None
        self.generative_params = {}

        # Optional per-track MIDI device (string name)
        self.midi_output_device = None

        self.steps = []
        for _ in range(step_count):
            self.steps.append({"active":0, "note":60, "velocity":100})

    def set_step_count(self, new_count):
        if new_count < 1:
            new_count = 1
        old_steps = self.steps
        self.steps = []
        for i in range(new_count):
            if i < len(old_steps):
                self.steps.append(old_steps[i])
            else:
                self.steps.append({"active":0, "note":60, "velocity":100})
        self.step_count = new_count

    def toggle_step(self, index):
        if 0 <= index < self.step_count:
            self.steps[index]["active"] = 1 - self.steps[index]["active"]

    def generate_pattern(self, reference_track=None):
        algo = self.algorithm
        if algo == "euclidean":
            pulses = self.generative_params.get("pulses",4)
            pat = generate_euclidean(self.step_count, pulses)
            for i,val in enumerate(pat):
                self.steps[i]["active"] = val
        elif algo == "random":
            prob = self.generative_params.get("probability_on",0.5)
            for i in range(self.step_count):
                self.steps[i]["active"] = 1 if random.random()<prob else 0
        elif algo == "markov":
            matrix = self.generative_params.get("transition_matrix",None)
            pat = generate_markov(self.step_count, matrix)
            for i,val in enumerate(pat):
                self.steps[i]["active"] = val
        elif algo == "rule_based":
            rule_name = self.generative_params.get("rule_name","simple")
            old_pat = [s["active"] for s in self.steps]
            new_pat = generate_rule_based(old_pat, rule_name)
            for i,val in enumerate(new_pat):
                self.steps[i]["active"] = val
        elif algo == "counterpoint":
            generate_species_counterpoint(self, reference_track, self.generative_params)
        else:
            # "none" => do nothing
            pass

###################################
# ALGORITHMS
###################################
def generate_euclidean(steps:int, pulses:int)->list:
    if steps<1:
        return []
    if pulses<1:
        return [0]*steps
    if pulses>steps:
        pulses=steps
    pattern=[]
    bucket=0
    for _ in range(steps):
        bucket += pulses
        if bucket>=steps:
            bucket-=steps
            pattern.append(1)
        else:
            pattern.append(0)
    return pattern

def generate_markov(steps:int, matrix=None)->list:
    if steps<1:
        return []
    if matrix is None:
        matrix = {
            0:{0:0.7,1:0.3},
            1:{0:0.4,1:0.6}
        }
    pat=[]
    cur=0 if random.random()<0.5 else 1
    for _ in range(steps):
        pat.append(cur)
        transitions = matrix.get(cur,{0:0.5,1:0.5})
        r=random.random()
        cum=0.0
        for nxt,prob in transitions.items():
            cum+=prob
            if r<cum:
                cur=nxt
                break
    return pat

def generate_rule_based(pat_in:list, rule_name:str)->list:
    out=pat_in[:]
    if rule_name=="simple":
        for i in range(len(out)):
            if i%2==0:
                out[i]=1-out[i]
    return out

def generate_species_counterpoint(target_track, reference_track, params):
    if not reference_track:
        return
    species = params.get("species","1st")
    intervals = params.get("intervals",[3,4,7,12])
    avoid_parallel = params.get("avoid_parallel", True)
    allow_leaps = (species!="1st")
    max_leap = 3 if not allow_leaps else 12

    prev_chosen=None
    prev_ref=None
    for i in range(target_track.step_count):
        ref_step = reference_track.steps[i % reference_track.step_count]
        ref_note = ref_step["note"]

        cands=[]
        for interval in intervals:
            cands.append(ref_note+interval)

        if avoid_parallel and prev_chosen is not None and prev_ref is not None:
            old_int = abs(prev_chosen - prev_ref)
            new_cands=[]
            for c in cands:
                new_int=abs(c - ref_note)
                if (old_int in (7,12)) and (new_int in (7,12)):
                    continue
                new_cands.append(c)
            cands=new_cands

        if prev_chosen is not None and not allow_leaps:
            cands=[x for x in cands if abs(x - prev_chosen)<=max_leap]

        chosen=ref_note
        if cands:
            chosen=random.choice(cands)

        target_track.steps[i]["note"]=chosen
        target_track.steps[i]["active"]=1
        prev_chosen=chosen
        prev_ref=ref_note
