import os
import re

class SMParser:
    @staticmethod
    def parse(filepath):
        """
        Parses a Stepmania .sm or .ssc chart file.
        Returns a song metadata dictionary in AutoDDR format, or None if failed.
        """
        if not os.path.exists(filepath):
            return None
            
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading chart file {filepath}: {e}")
            return None
            
        # Clean comments
        content = re.sub(r'//.*?\n', '\n', content)
        
        # Extract general header tags (TITLE, MUSIC, OFFSET, BPMS)
        tags = {}
        pattern = re.compile(r'#(\w+):([^;]*);', re.DOTALL)
        matches = pattern.findall(content)
        for tag, val in matches:
            t_upper = tag.upper()
            if t_upper in ["TITLE", "MUSIC", "OFFSET", "BPMS"]:
                tags[t_upper] = val.strip()
                
        title = tags.get("TITLE", os.path.basename(filepath).rsplit(".", 1)[0].replace("_", " "))
        music_file = tags.get("MUSIC", "")
        
        try:
            offset = float(tags.get("OFFSET", "0.0"))
        except ValueError:
            offset = 0.0
            
        # Parse BPMS (comma-separated list of beat=bpm)
        bpms_str = tags.get("BPMS", "0.000=120.000")
        bpms = []
        for pair in bpms_str.split(","):
            if "=" in pair:
                parts = pair.split("=")
                if len(parts) == 2:
                    try:
                        bpms.append((float(parts[0].strip()), float(parts[1].strip())))
                    except ValueError:
                        pass
        bpms.sort(key=lambda x: x[0])
        if not bpms:
            bpms = [(0.0, 120.0)]
            
        # Helper to convert beat number to absolute time (seconds)
        def beat_to_seconds(beat):
            t = 0.0
            curr_beat = 0.0
            curr_bpm = bpms[0][1]
            for i in range(1, len(bpms)):
                ch_beat, next_bpm = bpms[i]
                if beat <= ch_beat:
                    break
                t += (ch_beat - curr_beat) * 60.0 / curr_bpm
                curr_beat = ch_beat
                curr_bpm = next_bpm
            t += (beat - curr_beat) * 60.0 / curr_bpm
            return t - offset

        # Separate note blocks
        notes_blocks = []
        is_ssc = filepath.lower().endswith(".ssc")
        
        if is_ssc:
            # Split by #NOTEDATA:
            blocks = content.split("#NOTEDATA:")
            note_blocks_raw = blocks[1:] if len(blocks) > 1 else []
            for raw_block in note_blocks_raw:
                block_tags = {}
                matches = pattern.findall(raw_block)
                for tag, val in matches:
                    block_tags[tag.upper()] = val.strip()
                
                chart_type = block_tags.get("CHARTTYPE") or block_tags.get("STEPSTYPE") or ""
                difficulty = block_tags.get("DIFFICULTY", "")
                notes_data = block_tags.get("NOTES", "")
                
                if chart_type == "dance-single" and difficulty and notes_data:
                    # Construct pseudo-NOTES block matching the .sm split structure:
                    # dance-single : description : difficulty : rating : radar : notes_data
                    notes_blocks.append(f"dance-single : : {difficulty} : : : {notes_data}")
        else:
            # Standard .sm notes block parsing
            pos = 0
            while True:
                notes_start = content.upper().find("#NOTES:", pos)
                if notes_start == -1:
                    break
                notes_end = content.find(";", notes_start)
                if notes_end == -1:
                    break
                block_content = content[notes_start + 7 : notes_end]
                notes_blocks.append(block_content)
                pos = notes_end + 1
                
        charts = {
            "Easy": [],
            "Medium": [],
            "Hard": [],
            "Harder": [],
            "Crazy": []
        }
        
        # Stepmania to AutoDDR difficulty mapping
        diff_map = {
            "beginner": "Easy",
            "easy": "Easy",
            "medium": "Medium",
            "normal": "Medium",
            "hard": "Hard",
            "heavy": "Hard",
            "challenge": "Harder",
            "expert": "Crazy",
            "crazy": "Crazy",
            "insane": "Crazy",
            "edit": "Crazy"
        }
        
        # Parse notes inside note blocks
        for block in notes_blocks:
            fields = block.split(":")
            if len(fields) < 6:
                continue
                
            chart_type = fields[0].strip().lower()
            if chart_type != "dance-single":
                continue
                
            raw_diff = fields[2].strip().lower()
            target_diff = diff_map.get(raw_diff)
            if not target_diff:
                continue
                
            notes_data = fields[5].strip()
            
            # Split notes data by measures (separated by commas)
            measures = notes_data.split(",")
            current_beat = 0.0
            
            parsed_notes = []
            active_holds = {} # maps col (0-3) to start_time
            
            for m in measures:
                lines = [l.strip() for l in m.split("\n") if l.strip()]
                num_lines = len(lines)
                if num_lines == 0:
                    current_beat += 4.0
                    continue
                    
                beat_per_line = 4.0 / num_lines
                for idx, line in enumerate(lines):
                    # We expect exactly 4 columns for dance-single
                    if len(line) < 4:
                        continue
                        
                    line_beat = current_beat + idx * beat_per_line
                    line_time = beat_to_seconds(line_beat)
                    
                    for col in range(4):
                        char = line[col]
                        # 1: Tap note
                        if char == "1":
                            parsed_notes.append({
                                "time": float(round(line_time, 3)),
                                "lanes": [col],
                                "type": "single"
                            })
                        # 2: Hold head, 4: Roll head (start of hold)
                        elif char in ["2", "4"]:
                            active_holds[col] = line_time
                        # 3: Hold release (end of hold)
                        elif char == "3":
                            if col in active_holds:
                                start_t = active_holds[col]
                                end_t = line_time
                                parsed_notes.append({
                                    "time": float(round(start_t, 3)),
                                    "endtime": float(round(end_t, 3)),
                                    "lanes": [col],
                                    "type": "hold"
                                })
                                del active_holds[col]
                                
                current_beat += 4.0
                
            # Keep the chart with more notes if difficulty is defined multiple times
            if not charts[target_diff] or len(parsed_notes) > len(charts[target_diff]):
                charts[target_diff] = parsed_notes
                
        # Fill missing difficulties by copying the closest available parsed difficulty
        all_diffs = ["Easy", "Medium", "Hard", "Harder", "Crazy"]
        filled_diffs = [d for d in all_diffs if charts[d]]
        
        if not filled_diffs:
            print("No dance-single charts found in file.")
            return None
            
        for d in all_diffs:
            if not charts[d]:
                d_idx = all_diffs.index(d)
                closest_diff = min(filled_diffs, key=lambda x: abs(all_diffs.index(x) - d_idx))
                charts[d] = [dict(note) for note in charts[closest_diff]]
                
        # Estimate average BPM
        est_bpm = bpms[0][1] if bpms else 120.0
        
        return {
            "title": title,
            "filename": music_file,
            "bpm": round(est_bpm, 2),
            "duration": 0.0, # Filled dynamically during import after loading the audio file
            "charts": charts
        }
