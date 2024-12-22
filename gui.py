# gui.py

import tkinter as tk
from tkinter import ttk
import mido
from track import midi_to_note_name, note_name_to_midi, NOTE_NAMES, Track

GRID_CELL_SIZE = 30
GRID_CELL_GAP = 5

class GridSequencerGUI:
    def __init__(self, master, engine):
        self.master = master
        self.engine = engine
        self.master.title("New Grid Sequencer - Drag&Drop, Multi-track MIDI")
        self.master.geometry("1500x900")

        style = ttk.Style()
        style.theme_use("clam")

        # Top controls
        self.top_bar = ttk.Frame(self.master, padding=5)
        self.top_bar.pack(side="top", fill="x")
        self.build_top_bar()

        # Main area
        self.main_area = ttk.Frame(self.master)
        self.main_area.pack(side="top", fill="both", expand=True)

        # Left side: track order panel + "Add Track" button
        self.track_list_frame = ttk.Frame(self.main_area, width=200)
        self.track_list_frame.pack(side="left", fill="y", padx=5, pady=5)

        self.add_track_btn = ttk.Button(self.track_list_frame, text="+ Add Track", command=self.add_new_track)
        self.add_track_btn.pack(fill="x", pady=5)

        # We'll store a list of track "labels" that can be drag-and-drop reorder
        self.track_label_frames=[]
        self.dragging_track_idx = None  # for reorder

        # Middle: Canvas for steps
        self.canvas_frame = ttk.Frame(self.main_area)
        self.canvas_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#1e1e1e")
        self.canvas.pack(fill="both", expand=True)

        # Right: property panel for selected track
        self.prop_frame = ttk.Frame(self.main_area, width=300, padding=5)
        self.prop_frame.pack(side="right", fill="y")

        ttk.Label(self.prop_frame, text="Track Properties", font=("Arial",12,"bold")).pack(anchor="w", pady=5)

        # We'll store references for "selected track" for editing
        self.selected_track_idx=None
        self.selected_step_idx=None

        # Build track property sub-panel
        self.build_track_props_panel()
        # Step property sub-panel
        self.build_step_props_panel()

        # For storing canvas squares
        self.grid_cells={}
        self.active_steps={ i:-1 for i in range(len(self.engine.tracks)) }
        self.engine.on_step_callback=self.on_step_changed

        # Initially build track list UI
        self.rebuild_track_list()
        self.render_grid()

        self.refresh_ms=100
        self.master.after(self.refresh_ms, self.update_ui)

    # ---------------------------
    # Top Bar
    # ---------------------------
    def build_top_bar(self):
        ttk.Label(self.top_bar, text="BPM:").pack(side="left")
        self.bpm_var=tk.DoubleVar(value=self.engine.bpm)
        bpm_ent=ttk.Entry(self.top_bar, textvariable=self.bpm_var, width=6)
        bpm_ent.pack(side="left", padx=5)
        ttk.Button(self.top_bar, text="Set BPM", command=self.set_bpm).pack(side="left", padx=5)

        ttk.Button(self.top_bar, text="Play", command=self.engine.start).pack(side="left", padx=5)
        ttk.Button(self.top_bar, text="Stop", command=self.engine.stop).pack(side="left", padx=5)
        ttk.Button(self.top_bar, text="Generate All", command=self.engine.generate_all_tracks).pack(side="left", padx=5)

        out_lbl=ttk.Label(self.top_bar, text="Default MIDI Out:")
        out_lbl.pack(side="left", padx=5)
        outs=mido.get_output_names()
        self.global_out_var=tk.StringVar(value=outs[0] if outs else "")
        out_cb=ttk.Combobox(self.top_bar, textvariable=self.global_out_var, values=outs, width=18)
        out_cb.pack(side="left", padx=2)
        out_cb.bind("<<ComboboxSelected>>", self.on_global_out_changed)

        in_lbl=ttk.Label(self.top_bar, text="MIDI In:")
        in_lbl.pack(side="left", padx=5)
        ins=["Internal (No Clock)"]+mido.get_input_names()
        self.global_in_var=tk.StringVar(value=ins[0])
        in_cb=ttk.Combobox(self.top_bar, textvariable=self.global_in_var, values=ins, width=18)
        in_cb.pack(side="left", padx=2)
        in_cb.bind("<<ComboboxSelected>>", self.on_global_in_changed)

    def set_bpm(self):
        new_bpm=self.bpm_var.get()
        self.engine.set_bpm(new_bpm)

    def on_global_out_changed(self, event):
        dev=self.global_out_var.get()
        self.engine.set_midi_output_device(dev)

    def on_global_in_changed(self, event):
        dev=self.global_in_var.get()
        if dev=="Internal (No Clock)":
            self.engine.set_midi_input_device(None)
        else:
            self.engine.set_midi_input_device(dev)

    # ---------------------------
    # Track List + Drag-Drop
    # ---------------------------
    def rebuild_track_list(self):
        # First clear old
        for f in self.track_label_frames:
            f.destroy()
        self.track_label_frames=[]

        # Build new frames for each track
        for i, tr in enumerate(self.engine.tracks):
            fr=ttk.Frame(self.track_list_frame, padding=2, relief="ridge")
            fr.pack(fill="x", pady=2)
            lbl_txt=f"{tr.name} (Ch {tr.channel})"
            lbl=ttk.Label(fr, text=lbl_txt)
            lbl.pack(side="left")

            # Drag handlers
            fr.bind("<Button-1>", lambda e, idx=i: self.start_drag(idx, e))
            fr.bind("<B1-Motion>", lambda e, idx=i: self.do_drag(idx, e))
            fr.bind("<ButtonRelease-1>", lambda e, idx=i: self.end_drag(idx, e))

            self.track_label_frames.append(fr)

    def start_drag(self, idx, event):
        self.dragging_track_idx=idx

    def do_drag(self, idx, event):
        pass  # We won't do real-time reorder in motion; we do it on release

    def end_drag(self, idx, event):
        if self.dragging_track_idx is None:
            return
        release_y=event.y_root
        # figure out which track label is under release
        # We'll do a simple approach: check bounding boxes
        # We can compare the midpoints to reorder.

        # get the order in the track_list_frame
        children=self.track_list_frame.winfo_children()
        # find which child is nearest to release_y
        # Let's collect (child, y_top, y_bottom)
        positions=[]
        for i, child in enumerate(children):
            # bounding box in root coords
            x=self.track_list_frame.winfo_rootx()
            y=self.track_list_frame.winfo_rooty()
            child_y=child.winfo_y()
            child_h=child.winfo_height()
            top=y+child_y
            bot=top+child_h
            positions.append((i, top, bot, child))

        # find which child is at release_y
        new_index=None
        for (c_idx, c_top, c_bot, c_obj) in positions:
            if release_y>=c_top and release_y< c_bot:
                new_index=c_idx
                break
        if new_index is not None and new_index!=self.dragging_track_idx:
            self.engine.reorder_tracks(self.dragging_track_idx,new_index)
            self.rebuild_track_list()
            self.render_grid()

        self.dragging_track_idx=None

    def add_new_track(self):
        # create a new track with default name, random channel?
        ch=3+len(self.engine.tracks)  # just an example
        new_tr=Track(name=f"New Track {len(self.engine.tracks)+1}", step_count=8, channel=ch, subdivisions=4)
        self.engine.add_track(new_tr)
        self.rebuild_track_list()
        self.render_grid()

    # ---------------------------
    # Track Props
    # ---------------------------
    def build_track_props_panel(self):
        self.track_props_frame=ttk.LabelFrame(self.prop_frame, text="Track")
        self.track_props_frame.pack(fill="x", pady=5)

        # Algorithm
        ttk.Label(self.track_props_frame, text="Algorithm:").pack(anchor="w")
        self.algo_var=tk.StringVar(value="none")
        self.algo_cb=ttk.Combobox(self.track_props_frame, textvariable=self.algo_var,
                                  values=["none","euclidean","random","markov","rule_based","counterpoint"], width=15)
        self.algo_cb.pack(anchor="w", padx=5, pady=2)

        # Species
        ttk.Label(self.track_props_frame, text="Species (counterpoint):").pack(anchor="w")
        self.species_var=tk.StringVar(value="1st")
        self.species_cb=ttk.Combobox(self.track_props_frame, textvariable=self.species_var,
                                     values=["1st","2nd","3rd"], width=5)
        self.species_cb.pack(anchor="w", padx=5, pady=2)

        # Param
        ttk.Label(self.track_props_frame, text="Params (pulses=4; prob=0.5 ...):").pack(anchor="w")
        self.param_var=tk.StringVar(value="")
        param_ent=ttk.Entry(self.track_props_frame, textvariable=self.param_var, width=15)
        param_ent.pack(anchor="w", padx=5, pady=2)

        # Per-track MIDI out
        ttk.Label(self.track_props_frame, text="Track MIDI Out:").pack(anchor="w")
        outs=mido.get_output_names()
        self.track_out_var=tk.StringVar(value="")
        self.track_out_cb=ttk.Combobox(self.track_props_frame, textvariable=self.track_out_var,
                                       values=outs, width=18)
        self.track_out_cb.pack(anchor="w", padx=5, pady=2)

        # Apply
        apply_btn=ttk.Button(self.track_props_frame, text="Apply Track", command=self.apply_track_changes)
        apply_btn.pack(anchor="e", pady=5)

    # ---------------------------
    # Step Props
    # ---------------------------
    def build_step_props_panel(self):
        self.step_props_frame=ttk.LabelFrame(self.prop_frame, text="Step")
        self.step_props_frame.pack(fill="x", pady=5)

        ttk.Label(self.step_props_frame, text="Note:").pack(anchor="w")
        self.step_note_var=tk.StringVar(value="C4")
        self.step_note_cb=ttk.Combobox(self.step_props_frame, textvariable=self.step_note_var,
                                       values=NOTE_NAMES, width=8)
        self.step_note_cb.pack(anchor="w", padx=5, pady=2)

        ttk.Label(self.step_props_frame, text="Velocity:").pack(anchor="w")
        self.step_vel_var=tk.IntVar(value=100)
        step_vel_ent=ttk.Entry(self.step_props_frame, textvariable=self.step_vel_var, width=6)
        step_vel_ent.pack(anchor="w", padx=5, pady=2)

        apply_btn=ttk.Button(self.step_props_frame, text="Apply Step", command=self.apply_step_changes)
        apply_btn.pack(anchor="e", pady=5)

    def apply_track_changes(self):
        """
        Grab the user input for selected track and apply changes (algo, species, param, track midi out).
        Then regenerate pattern if needed.
        """
        if self.selected_track_idx is None or self.selected_track_idx>=len(self.engine.tracks):
            return
        track=self.engine.tracks[self.selected_track_idx]
        # algo
        a=self.algo_var.get()
        track.algorithm=None if a=="none" else a
        # species
        if track.algorithm=="counterpoint":
            track.generative_params["species"]=self.species_var.get()
        else:
            track.generative_params.pop("species",None)

        # parse param
        p_text=self.param_var.get().strip()
        if p_text:
            # e.g. "pulses=4;prob=0.5"
            entries=p_text.split(";")
            for e in entries:
                e=e.strip()
                if "=" in e:
                    k,v=e.split("=")
                    k=k.strip()
                    v=v.strip()
                    try:
                        if "." in v:
                            val=float(v)
                        else:
                            val=int(v)
                        track.generative_params[k]=val
                    except ValueError:
                        track.generative_params[k]=v

        # track midi out
        out_val=self.track_out_var.get().strip()
        if out_val:
            track.midi_output_device=out_val
        else:
            track.midi_output_device=None

        # re-generate if needed
        if track.algorithm=="counterpoint":
            ref = self.engine.tracks[0] if len(self.engine.tracks)>0 else None
            track.generate_pattern(reference_track=ref)
        else:
            track.generate_pattern()
        self.render_grid()

    def apply_step_changes(self):
        """
        Apply note/velocity to the selected step
        """
        if self.selected_track_idx is None or self.selected_step_idx is None:
            return
        if self.selected_track_idx>=len(self.engine.tracks):
            return
        track=self.engine.tracks[self.selected_track_idx]
        if self.selected_step_idx>=track.step_count:
            return

        step_data=track.steps[self.selected_step_idx]
        step_data["note"]=note_name_to_midi(self.step_note_var.get())
        step_data["velocity"]=self.step_vel_var.get()

        # If active, recolor
        rect_id=self.grid_cells.get((self.selected_track_idx,self.selected_step_idx))
        if rect_id:
            self.canvas.itemconfig(rect_id, fill=self.get_step_color(step_data))

    # ---------------------------
    # GRID RENDERING
    # ---------------------------
    def render_grid(self):
        self.canvas.delete("all")
        self.grid_cells.clear()

        y_offset=20
        for t_idx, track in enumerate(self.engine.tracks):
            label_txt=f"{track.name} (Ch {track.channel})"
            self.canvas.create_text(10, y_offset+GRID_CELL_SIZE/2, text=label_txt, anchor="w",
                                    fill="#ffffff", font=("Arial",11,"bold"))
            x_offset=200
            for s_idx, step_data in enumerate(track.steps):
                x1=x_offset
                y1=y_offset
                x2=x1+GRID_CELL_SIZE
                y2=y1+GRID_CELL_SIZE
                fill_color=self.get_step_color(step_data)
                rect_id=self.canvas.create_rectangle(x1,y1,x2,y2, fill=fill_color, outline="#000000")
                self.grid_cells[(t_idx,s_idx)]=rect_id

                self.canvas.tag_bind(rect_id, "<Button-1>",
                                     lambda e, tr_i=t_idx, st_i=s_idx: self.toggle_step(tr_i,st_i))
                self.canvas.tag_bind(rect_id, "<Double-Button-1>",
                                     lambda e, tr_i=t_idx, st_i=s_idx: self.select_step(tr_i,st_i))

                x_offset+=(GRID_CELL_SIZE+GRID_CELL_GAP)
            y_offset+=(GRID_CELL_SIZE+30)

    def get_step_color(self, step_data):
        if step_data["active"]==0:
            return "#333333"
        else:
            vel=step_data["velocity"]
            brightness=hex(min(255,max(40,vel)))[2:].zfill(2)
            return f"#00{brightness}00"

    def toggle_step(self, track_idx, step_idx):
        if track_idx<0 or track_idx>=len(self.engine.tracks):
            return
        track=self.engine.tracks[track_idx]
        track.toggle_step(step_idx)
        cell_id=self.grid_cells.get((track_idx,step_idx))
        new_color=self.get_step_color(track.steps[step_idx])
        if cell_id:
            self.canvas.itemconfig(cell_id, fill=new_color)

    def select_step(self, track_idx, step_idx):
        """
        Mark track & step as 'selected' => fill side panel
        """
        self.selected_track_idx=track_idx
        self.selected_step_idx=step_idx

        track=self.engine.tracks[track_idx]
        # fill track props
        algo=track.algorithm if track.algorithm else "none"
        self.algo_var.set(algo)
        if algo=="counterpoint":
            sp=track.generative_params.get("species","1st")
            self.species_var.set(sp)
        else:
            self.species_var.set("1st")

        # fill param
        # we won't attempt to parse back into text, let's leave blank or partial
        self.param_var.set("")

        # track MIDI out
        if track.midi_output_device:
            self.track_out_var.set(track.midi_output_device)
        else:
            self.track_out_var.set("")

        # fill step data
        if step_idx<track.step_count:
            step_data=track.steps[step_idx]
            self.step_note_var.set(midi_to_note_name(step_data["note"]))
            self.step_vel_var.set(step_data["velocity"])

    # ---------------------------
    # ENGINE CALLBACK + LOOP
    # ---------------------------
    def on_step_changed(self, track_idx, new_step):
        self.active_steps[track_idx]=new_step

    def update_ui(self):
        if self.engine.playing:
            for (t_i, s_i), rect_id in self.grid_cells.items():
                if s_i==self.active_steps.get(t_i,-1):
                    self.canvas.itemconfig(rect_id, outline="#FFFF00", width=2)
                else:
                    self.canvas.itemconfig(rect_id, outline="#000000", width=1)
        else:
            # not playing => remove highlights
            for rect_id in self.grid_cells.values():
                self.canvas.itemconfig(rect_id, outline="#000000", width=1)

        self.master.after(self.refresh_ms, self.update_ui)
